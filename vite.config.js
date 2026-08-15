import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: resolve(
      __dirname,
      "src/geo_activity_playground/webui/static/dist",
    ),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        app: resolve(__dirname, "frontend/src/app.js"),
        "map-layers": resolve(__dirname, "frontend/src/map-layers.js"),
        "server-side-explorer": resolve(
          __dirname,
          "frontend/src/server-side-explorer.js",
        ),
        "activity-trim": resolve(__dirname, "frontend/src/activity-trim.js"),
      },
      // Entries' exports are consumed by inline `<script type="module">import
      // ... from '/static/dist/...'</script>` blocks in Jinja templates,
      // invisible to Rollup's own module graph. Without this, Rollup
      // tree-shakes those exports away as apparently unused.
      preserveEntrySignatures: "strict",
      output: {
        // Entry filenames are referenced directly from Jinja templates, so
        // they must stay fixed. Shared chunks are only ever referenced via
        // import statements inside the entries themselves, so they can (and,
        // to avoid colliding with an entry name, must) be hashed.
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "[name].[ext]",
      },
    },
  },
});
