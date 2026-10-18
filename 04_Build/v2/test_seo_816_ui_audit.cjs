#!/usr/bin/env node
// #816 static safety contract: SEO-only UI improvements; no browser network access.
const fs=require('fs'),assert=require('assert');
const src=fs.readFileSync('05_V2.0.0_Source/web/r8_13_seo_geo.html','utf8');
assert(src.includes('seo816-audit-details'),'SEO audit panel missing');
assert(src.includes('历史检测·待更新'),'stale evidence warning missing');
assert(src.includes('auto.last_error'),'automatic-audit failure feedback missing');
assert(src.includes('/api/r8-13/seo-geo/audit-site'),'manual real-audit control missing');
const geo=fs.readFileSync('05_V2.0.0_Source/browser_extension/kazuizhi_geo/manifest.json','utf8');
assert(JSON.parse(geo).version==='2.2.2.814','GEO extension must remain 814');
console.log('#816 SEO-only interface contract passed, GEO extension unchanged');
