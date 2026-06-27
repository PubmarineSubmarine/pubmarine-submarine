import * as esbuild from "esbuild";

const isWatch = process.argv.includes("--watch");

const commonOptions = {
  bundle: true,
  format: "esm",
  target: "es2020",
  jsx: "transform",
  jsxFactory: "h",
  jsxFragment: "Fragment",
  inject: ["./src/js/preact-shim.js"],
  minify: !isWatch,
  sourcemap: isWatch ? "inline" : false,
  treeShaking: true,
};

const entryPoints = [
  {
    in: "src/js/gamepad-app.jsx",
    out: "gamepad",
  },
  {
    in: "src/js/console-app.jsx",
    out: "console",
  },
];

const buildOptions = {
  ...commonOptions,
  entryPoints: entryPoints,
  outdir: "static/js",
  entryNames: "[name].bundle",
};

if (isWatch) {
  const ctx = await esbuild.context(buildOptions);
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  await esbuild.build(buildOptions);
  console.log("Build complete → static/js/{gamepad,console}.bundle.js");
}
