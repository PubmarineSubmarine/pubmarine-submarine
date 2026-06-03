import * as esbuild from "esbuild";

const isWatch = process.argv.includes("--watch");

const buildOptions = {
  entryPoints: ["src/js/gamepad-app.jsx"],
  bundle: true,
  outfile: "static/js/gamepad.bundle.js",
  format: "esm",
  target: "es2020",
  // Classic JSX transform — compiles <div/> to h("div")
  jsx: "transform",
  jsxFactory: "h",
  jsxFragment: "Fragment",
  // Inject Preact's h and Fragment as global shims so the factory calls resolve
  inject: ["./src/js/preact-shim.js"],
  minify: !isWatch,
  sourcemap: isWatch ? "inline" : false,
  treeShaking: true,
};

if (isWatch) {
  const ctx = await esbuild.context(buildOptions);
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  await esbuild.build(buildOptions);
  console.log("Build complete → static/js/gamepad.bundle.js");
}
