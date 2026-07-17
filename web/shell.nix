{ pkgs ? import <nixpkgs> {} }:

let
  # Libraries that pre-built Python wheels (manylinux) need at runtime on
  # NixOS. Add more here if other compiled deps have similar issues.
  fhsLibs = with pkgs; [
    stdenv.cc.cc       # libstdc++.so.6 (numpy, pyserial asyncio, etc.)
    zlib               # libz.so.1
    stdenv.cc.cc.lib   # libgcc_s.so.1
  ];
in

pkgs.mkShell {
  packages = with pkgs; [
    python313
    uv
  ];

  # For Python C extensions loaded via dlopen (numpy .so files).
  # This is sufficient on NixOS without needing programs.nix-ld
  # system-wide.
  LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath fhsLibs;

  # Also set the nix-ld vars so it works either way.
  NIX_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath fhsLibs;
  NIX_LD = "${pkgs.stdenv.cc.bintools.dynamicLinker}";

  shellHook = ''
    export UV_PYTHON="$(command -v python3)"
    echo "dev shell ready."
    echo ""
    echo "   uv sync"
    echo "   uv run app/main.py --host 0.0.0.0 --port 8000"
    echo ""
    echo "  (debug mode — no sub hardware needed:)"
    echo "   SERIAL_PORT=DEBUG uv run app/main.py --host 0.0.0.0 --port 8000"
  '';
}
