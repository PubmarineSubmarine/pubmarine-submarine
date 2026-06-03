// This shim is injected by esbuild so that JSX factory calls (h, Fragment) resolve correctly.
import { h, Fragment } from "preact";
export { h, Fragment };
