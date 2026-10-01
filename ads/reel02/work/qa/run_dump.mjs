// QA only: bundle dump_cues.ts (+ the real remotion/src modules it imports) with esbuild and run it.
import {build} from '../../remotion/node_modules/esbuild/lib/main.js';
import {execFileSync} from 'child_process';
import {dirname, join} from 'path';
import {fileURLToPath} from 'url';

const here = dirname(fileURLToPath(import.meta.url));
const outfile = join(here, 'build', 'dump_cues.cjs');
await build({
  entryPoints: [join(here, 'dump_cues.ts')],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  outfile,
  loader: {'.json': 'json'},
  nodePaths: [join(here, '..', '..', 'remotion', 'node_modules')],
  logLevel: 'warning',
});
execFileSync('node', [outfile, join(here, 'cues_dump.json')], {stdio: 'inherit'});
