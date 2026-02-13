import { build } from 'esbuild';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

const entryFile = path.join(
  repoRoot,
  'app/static/js/tools/soaps/soap_tool_bundle_entry.js',
);
const outputDir = path.join(repoRoot, 'app/static/js/tools/soaps');

const sharedConfig = {
  entryPoints: [entryFile],
  bundle: true,
  format: 'iife',
  target: ['es2019'],
  platform: 'browser',
  legalComments: 'none',
  logLevel: 'info',
};

async function run(){
  await build({
    ...sharedConfig,
    outfile: path.join(outputDir, 'soap_tool_bundle.min.js'),
    minify: true,
    sourcemap: false,
  });
}

run().catch(error => {
  console.error(error);
  process.exit(1);
});
