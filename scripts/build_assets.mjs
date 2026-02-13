import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const staticRoot = path.join(repoRoot, 'app', 'static');
const distRoot = path.join(staticRoot, 'dist');
const manifestPath = path.join(distRoot, 'manifest.json');

const ENTRY_SPECS = [
  { request: 'js/components/suggestions.js', source: 'js/components/suggestions.js', format: 'iife', scope: 'core' },
  { request: 'js/components/tool_lines.js', source: 'js/components/tool_lines.js', format: 'iife', scope: 'core' },
  { request: 'js/subscription_tiers.js', source: 'js/subscription_tiers.js', format: 'iife', scope: 'core' },
  { request: 'js/utils/utils.js', source: 'js/utils/utils.js', format: 'iife', scope: 'core' },
  { request: 'js/inventory/inventory_adjust.js', source: 'js/inventory/inventory_adjust.js', format: 'iife', scope: 'core' },
  { request: 'js/conversion/unit_converter.js', source: 'js/conversion/unit_converter.js', format: 'iife', scope: 'core' },
  { request: 'js/drawers/container_unit_mismatch_drawer.js', source: 'js/drawers/container_unit_mismatch_drawer.js', format: 'iife', scope: 'core' },
  { request: 'js/expiration_alerts.js', source: 'js/expiration_alerts.js', format: 'iife', scope: 'core' },
  { request: 'js/batches/batch_form.js', source: 'js/batches/batch_form.js', format: 'iife', scope: 'core' },
  { request: 'js/batches/fifo_modal.js', source: 'js/batches/fifo_modal.js', format: 'iife', scope: 'core' },
  { request: 'js/inventory/inventory_view.js', source: 'js/inventory/inventory_view.js', format: 'iife', scope: 'core' },
  { request: 'js/organization/dashboard.js', source: 'js/organization/dashboard.js', format: 'iife', scope: 'core' },
  { request: 'js/products/product_inventory.js', source: 'js/products/product_inventory.js', format: 'iife', scope: 'core' },
  { request: 'js/recipes/recipe_form.js', source: 'js/recipes/recipe_form.js', format: 'iife', scope: 'core' },
  { request: 'js/recipes/skins/category_skins.js', source: 'js/recipes/skins/category_skins.js', format: 'iife', scope: 'core' },
  { request: 'js/recipes/skins/baking_skin.js', source: 'js/recipes/skins/baking_skin.js', format: 'iife', scope: 'core' },
  { request: 'js/recipes/skins/cosmetics_skin.js', source: 'js/recipes/skins/cosmetics_skin.js', format: 'iife', scope: 'core' },
  { request: 'js/global_item_stats.js', source: 'js/global_item_stats.js', format: 'esm', scope: 'core' },
  { request: 'js/core/SessionGuard.js', source: 'js/core/SessionGuard.js', format: 'esm', scope: 'core' },
  { request: 'js/core/DrawerProtocol.js', source: 'js/core/DrawerProtocol.js', format: 'esm', scope: 'core' },
  { request: 'js/core/DrawerInterceptor.js', source: 'js/core/DrawerInterceptor.js', format: 'esm', scope: 'core' },
  { request: 'js/main.js', source: 'js/main.js', format: 'esm', scope: 'core' },
  { request: 'js/drawers/drawer_cadence.js', source: 'js/drawers/drawer_cadence.js', format: 'esm', scope: 'core' },
  { request: 'js/production_planning/plan_production.js', source: 'js/production_planning/plan_production.js', format: 'esm', scope: 'core' },
  { request: 'js/tools/soaps/soap_tool_bundle_entry.js', source: 'js/tools/soaps/soap_tool_bundle_entry.js', format: 'esm', scope: 'soap' },
];

function toPosix(relativePath){
  return relativePath.split(path.sep).join('/');
}

function parseScopeArg(){
  const scopeArg = process.argv.find(arg => arg.startsWith('--scope='));
  if (!scopeArg) return null;
  const scope = String(scopeArg.split('=')[1] || '').trim();
  return scope || null;
}

async function runBuildForFormat({ specs, format }){
  if (!specs.length) return {};
  const entryPoints = specs.map(spec => path.join(staticRoot, spec.source));
  const sourceToRequest = new Map(specs.map(spec => [spec.source, spec.request]));

  const result = await build({
    entryPoints,
    outdir: distRoot,
    outbase: staticRoot,
    entryNames: '[dir]/[name]-[hash]',
    bundle: true,
    minify: true,
    sourcemap: false,
    legalComments: 'none',
    logLevel: 'info',
    platform: 'browser',
    target: ['es2019'],
    format,
    metafile: true,
  });

  const formatManifest = {};
  const outputs = result.metafile?.outputs || {};
  for (const [outfile, metadata] of Object.entries(outputs)) {
    if (!metadata.entryPoint) continue;
    const sourceRel = toPosix(path.relative(staticRoot, metadata.entryPoint));
    const requestKey = sourceToRequest.get(sourceRel);
    if (!requestKey) continue;
    const outRel = toPosix(path.relative(staticRoot, outfile));
    formatManifest[requestKey] = outRel;
  }
  return formatManifest;
}

async function run(){
  const scopeFilter = parseScopeArg();
  const selectedSpecs = scopeFilter
    ? ENTRY_SPECS.filter(spec => spec.scope === scopeFilter)
    : ENTRY_SPECS.slice();

  if (!selectedSpecs.length) {
    throw new Error(`No asset entries matched scope "${scopeFilter}"`);
  }

  const cleanDist = !scopeFilter;
  if (cleanDist) {
    fs.rmSync(distRoot, { recursive: true, force: true });
  }
  fs.mkdirSync(distRoot, { recursive: true });

  const iifeSpecs = selectedSpecs.filter(spec => spec.format === 'iife');
  const esmSpecs = selectedSpecs.filter(spec => spec.format === 'esm');

  const iifeManifest = await runBuildForFormat({ specs: iifeSpecs, format: 'iife' });
  const esmManifest = await runBuildForFormat({ specs: esmSpecs, format: 'esm' });
  const nextManifest = { ...iifeManifest, ...esmManifest };

  let manifest = {};
  if (!cleanDist && fs.existsSync(manifestPath)) {
    const existingRaw = fs.readFileSync(manifestPath, 'utf8');
    manifest = JSON.parse(existingRaw);
  }
  manifest = { ...manifest, ...nextManifest };

  const sorted = Object.fromEntries(
    Object.entries(manifest).sort(([a], [b]) => a.localeCompare(b)),
  );
  fs.writeFileSync(manifestPath, `${JSON.stringify(sorted, null, 2)}\n`, 'utf8');
  console.log(`Wrote asset manifest: ${toPosix(path.relative(repoRoot, manifestPath))}`);
}

run().catch(error => {
  console.error(error);
  process.exit(1);
});
