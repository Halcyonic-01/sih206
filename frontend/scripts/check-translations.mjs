// Repeatable literal-key coverage check; no source rewriting and no network.
import ts from 'typescript';
import fs from 'node:fs';
import path from 'node:path';
const dictionary={};
for(const file of ['hi','hi-help','hi-domain','hi-dynamic'])Object.assign(dictionary,JSON.parse(fs.readFileSync(`src/i18n/${file}.json`,'utf8')));
const keys=new Set();
function files(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)):[path.join(dir,e.name)]);}
for(const file of files('src').filter(f=>/\.tsx?$/.test(f)&&!f.includes('.test.'))){
 const ast=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,file.endsWith('tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
 function visit(n){if(ts.isCallExpression(n)&&['tr','t'].includes(n.expression.getText(ast))&&n.arguments[0]&&ts.isStringLiteral(n.arguments[0]))keys.add(n.arguments[0].text.trim());ts.forEachChild(n,visit);}
 visit(ast);
}
const missing=[...keys].filter(key=>!dictionary[key]||!/[\u0900-\u097f]/.test(dictionary[key]));
if(missing.length){console.error('Missing Hindi translations:',missing);process.exitCode=1;}
else console.log(`Hindi coverage passed for ${keys.size} explicit UI keys; ${Object.keys(dictionary).length} catalog entries.`);
