(async function(){
  const fetch = global.fetch || require('node-fetch');
  const API = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000/api/v1';

  function parseMagnitude(num, unit){
    const v = parseFloat(num.replace(/,/g, ''));
    const u = (unit||'').toLowerCase();
    if (u === 'bn' || u === 'billion' || u === 'b') return v * 1000;
    return v;
  }

  function extractFromText(text){
    const t = text.toLowerCase().replace(/,/g,'');
    const out = {};
    // revenue context patterns
    const revContextPatterns = [
      /revenue[^\d$]*\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?/i,
      /\$\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?\s*(?:in\s+)?revenue/i,
      /(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?\s*(?:in\s+)?(?:revenue|turnover|sales)/i,
    ];
    for(const p of revContextPatterns){
      const m = t.match(p);
      if(m){ out.revenue = parseMagnitude(m[1], m[2]||''); break; }
    }
    // cost context patterns
    const costContextPatterns = [
      /(?:operating\s+)?costs?\s+(?:at|of|around|is|are)\s+\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?/i,
      /\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?\s*(?:in\s+)?(?:operating\s+)?costs?/i,
      /(?:expenses?|opex|expenditure)\s+(?:of|at|around|is)?\s*\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?/i,
      /\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)\s+(?:in\s+)?(?:costs?|opex|expenses?)/i,
    ];
    for(const p of costContextPatterns){
      const m = t.match(p);
      if(m){ out.cost = parseMagnitude(m[1], m[2]||''); break; }
    }
    // standalone compact like "1bn" -> revenue only if revenue undefined
    if(out.revenue === undefined){
      const standaloneM = t.match(/^\s*\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)\s*$/i);
      if(standaloneM) out.revenue = parseMagnitude(standaloneM[1], standaloneM[2]);
    }
    // margin patterns
    const marginPatterns = [
      /margin\s*(?:at|of|around|is|:)?\s*(\d+(?:\.\d+)?)\s*%?/i,
      /(\d+(?:\.\d+)?)\s*%\s*(?:operating\s+)?margin/i,
      /(\d+(?:\.\d+)?)\s*(?:%|percent)\s*(?:margin)?/i,
    ];
    for(const p of marginPatterns){
      const m = t.match(p);
      if(m){ const v = parseFloat(m[1]); if(v>=0 && v<=100){ out.margin = v; break; } }
    }
    // debt patterns
    const debtPatterns = [
      /(?:technical\s+)?debt\s*(?:at|of|around|is|:)?\s*(\d+(?:\.\d+)?)\s*%?/i,
      /(\d+(?:\.\d+)?)\s*%\s*(?:technical\s+)?debt/i,
    ];
    for(const p of debtPatterns){
      const m = t.match(p);
      if(m){ out.technicalDebt = parseFloat(m[1]); break; }
    }
    // keyword heuristics
    if(out.technicalDebt === undefined){
      if(/very\s+high\s+(?:technical\s+)?debt|huge\s+(?:technical\s+)?debt|legacy\s+stack/.test(t)) out.technicalDebt = 92;
      else if(/high\s+(?:technical\s+)?debt/.test(t)) out.technicalDebt = 78;
      else if(/moderate\s+(?:technical\s+)?debt/.test(t)) out.technicalDebt = 50;
      else if(/low\s+(?:technical\s+)?debt/.test(t)) out.technicalDebt = 20;
    }
    return out;
  }

  function applyBareNumber(value, collected, targetField){
    if(!targetField){
      const order = ['revenue','cost','margin','technicalDebt'];
      for(const f of order) if(collected[f]===undefined) { targetField=f; break; }
    }
    if(!targetField) return {};
    if(targetField==='revenue') return { revenue: value < 10 ? value*1000 : value };
    if(targetField==='cost') return { cost: value < 10 ? value*1000 : value };
    if(targetField==='margin') return { margin: value };
    if(targetField==='technicalDebt') return { technicalDebt: value };
    return {};
  }

  // Simulated conversation
  const collected = {};
  const description = "I need a transformation. telecom operator, huge opex and no profit";
  console.log('Step 1: user says description:', description);
  const inferred = extractFromText(description);
  // treat description as companyContext; use inferred values only for fields present
  Object.assign(collected, inferred);
  console.log('Parsed after description:', JSON.stringify(collected, null, 2));

  // Step 2: user replies '1bn'
  const step2 = '1bn';
  console.log('\nStep 2: user replies:', step2);
  const ext2 = extractFromText(step2);
  if(Object.keys(ext2).length===0){
    // standalone compact should be handled by extractFromText; but if not, try parse
  }
  if(ext2.revenue) collected.revenue = ext2.revenue;
  console.log('Parsed after 1bn:', JSON.stringify(collected, null, 2));

  // Next field expected according to frontend order: cost, margin, technicalDebt.
  // But user next replies '23' which is bare number; frontend would map bare number to lastAskedField (we'll assume margin asked), so map to margin.
  const step3 = '23';
  console.log('\nStep 3: user replies:', step3);
  const bare = parseFloat(step3.replace(/[%$,]/g,''));
  if(!isNaN(bare)){
    const applied = applyBareNumber(bare, collected, 'margin');
    Object.assign(collected, applied);
  }
  console.log('Parsed after 23:', JSON.stringify(collected, null, 2));

  // Build final body text as frontend would
  const bodyText = [
    description,
    `Revenue: ${collected.revenue || 800}M`,
    `Operating costs: ${collected.cost || 250}M`,
    `Margin: ${collected.margin || 15}%`,
    `Technical debt: ${collected.technicalDebt || 60}%`,
  ].join('. ');

  console.log('\nFinal POST bodyText:\n', bodyText);

  // POST to backend intake
  try{
    const resp = await fetch(API + '/intake', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tenant_id: 'x', model_version_id: '', text: bodyText }),
    });
    const j = await resp.json();
    console.log('\nBackend /intake response:');
    console.log(JSON.stringify(j, null, 2));
  } catch(err){
    console.error('Request failed:', err.message || err);
    process.exitCode = 2;
  }
})();
