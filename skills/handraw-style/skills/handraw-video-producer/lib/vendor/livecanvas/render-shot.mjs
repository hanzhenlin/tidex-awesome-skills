// Adapted from LiveCanvas a04f18f render.mjs. MIT, see LICENSE.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {selectComposition,renderMedia} from '@remotion/renderer';
const job=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
const modules=path.join(path.dirname(fileURLToPath(import.meta.url)),'node_modules');
const aliases=Object.fromEntries(['react','react-dom','remotion'].map(x=>[x,path.join(modules,x)]));
const serveUrl=await bundle({entryPoint:job.entry,publicDir:job.publicDir,webpackOverride:config=>({...config,resolve:{...config.resolve,modules:[modules,'node_modules'],alias:{...config.resolve?.alias,...aliases}}})});
const browserExecutable=process.env.HVP_BROWSER;
const composition=await selectComposition({serveUrl,id:'LiveCanvas',inputProps:job.props,browserExecutable});
await renderMedia({serveUrl,composition,inputProps:job.props,browserExecutable,codec:'h264',pixelFormat:'yuv420p',outputLocation:job.output,concurrency:2});
