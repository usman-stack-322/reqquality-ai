import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join } from 'node:path';
import React from 'react';
import { renderToString } from 'react-dom/server';

test('revision preview separates saved and new cases, highlights differences and escapes provider text',async()=>{
  const directory=await mkdtemp(new URL('../.render-test-',import.meta.url));
  try{
    const output=await build({entryPoints:[fileURLToPath(new URL('./components/AIReviewAssistant.jsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'esm',packages:'external'});
    const filename=pathToFileURL(join(directory,'Review.mjs'));await writeFile(filename,output.outputFiles[0].contents);
    const {ProposalPreview}=await import(filename.href);
    const saved={id:5,case_revision:3,title:'Original',test_steps:['Existing step'],expected_result:'Saved result'};
    const turn={base_snapshot:{test_cases:[saved]},proposal:{changes:[{operation:'revise',case_id:5,summary:'Clearer result',content:{...saved,expected_result:'<script>unsafe()</script>'}},{operation:'new',case_id:0,summary:'Missing scenario',content:{title:'New case',test_steps:['New step'],expected_result:'New result'}}]}};
    const html=renderToString(React.createElement(ProposalPreview,{turn}));
    for(const value of ['Saved version','Proposed version','Pending Review','NEW proposed test case','Saved result','ai-changed','&lt;script&gt;'])assert.ok(html.includes(value),value);
    assert.ok(!html.includes('<script>'));
    assert.equal(saved.expected_result,'Saved result');
  }finally{await rm(directory,{recursive:true,force:true});}
});
