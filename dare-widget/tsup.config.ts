import { defineConfig } from "tsup";

export default defineConfig({
  // The single public entry point. tsup follows every import from here and
  // bundles the reachable src/ files into one output per format.
  entry: ["src/index.ts"],

  // Emit both module formats promised in package.json's "exports":
  //   esm -> dist/index.js   (modern bundlers: Vite/webpack)
  //   cjs -> dist/index.cjs  (older Node/tooling that uses require)
  format: ["esm", "cjs"],

  // Generate dist/index.d.ts — the TypeScript declarations that give the
  // host app autocomplete and prop type-checking on <DareWidget .../>.
  dts: true,

  // Do NOT bundle React into our output. It's a peerDependency: the host app
  // supplies it at runtime, and bundling a second copy would break hooks.
  external: ["react", "react-dom"],

  // Drop unused exports from the final bundle (pairs with sideEffects:false).
  treeshake: true,

  // Ship source maps so a consumer debugging their app can step into readable
  // widget source instead of minified output.
  sourcemap: true,

  // Wipe dist/ before each build so stale files never linger.
  clean: true,

  // Match tsconfig's target: browsers running a React app.
  target: "es2020",
});
