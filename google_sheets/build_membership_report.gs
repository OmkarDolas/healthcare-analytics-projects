/**
 * Google Sheets version of the Membership Report.
 *
 * Setup (about 1 minute):
 *   1. Create a blank Google Sheet (sheets.new).
 *   2. Extensions > Apps Script, paste this file, save.
 *   3. Run buildMembershipReport once and approve the permissions prompt
 *      (it only reads the CSVs from this GitHub branch and writes to this spreadsheet).
 *   4. Reload the sheet: a "Membership Report" menu appears for refreshes.
 *
 * Builds: Data / Products / Budget tabs, a Report tab driven by dropdowns (data validation) with
 * SUMIFS, XLOOKUP, INDEX-MATCH and VLOOKUP formulas, a QUERY summary tab, a pivot table, and
 * conditional formatting on budget variance.
 */
const BASE = 'https://raw.githubusercontent.com/OmkarDolas/healthcare-analytics-projects/' +
             'membership-reporting-forecasting-dashboard/outputs/google_sheets/';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Membership Report')
    .addItem('Refresh data and rebuild', 'buildMembershipReport')
    .addToUi();
}

function buildMembershipReport() {
  const ss = SpreadsheetApp.getActive();
  const data = loadCsv_(ss, 'Data', 'data.csv', [0], [3, 4, 5, 6, 7, 8, 9]);
  loadCsv_(ss, 'Products', 'products.csv', [], []);
  const budget = loadCsv_(ss, 'Budget', 'budget.csv', [0], [2, 3]);
  addBudgetVariance_(ss.getSheetByName('Budget'), budget);
  buildReport_(ss, data);
  buildQuery_(ss);
  buildPivot_(ss, data);
  ['Report', 'Pivot', 'Query', 'Data', 'Products', 'Budget'].forEach(function (name, i) {
    ss.setActiveSheet(ss.getSheetByName(name));
    ss.moveActiveSheet(i + 1);
  });
  const blank = ss.getSheetByName('Sheet1');
  if (blank) ss.deleteSheet(blank);
  ss.setActiveSheet(ss.getSheetByName('Report'));
}

/** Fetch a CSV from GitHub into a fresh tab, converting date and numeric columns. Returns row count. */
function loadCsv_(ss, name, file, dateCols, numCols) {
  const rows = Utilities.parseCsv(UrlFetchApp.fetch(BASE + file).getContentText());
  const body = rows.slice(1).map(function (r) {
    return r.map(function (v, c) {
      if (dateCols.indexOf(c) >= 0) { const p = v.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
      if (numCols.indexOf(c) >= 0) return v === '' ? '' : Number(v);
      return v;
    });
  });
  const sh = ss.getSheetByName(name) || ss.insertSheet(name);
  sh.clear();
  sh.getRange(1, 1, 1, rows[0].length).setValues([rows[0]]).setFontWeight('bold')
    .setBackground('#1F3864').setFontColor('#FFFFFF');
  sh.getRange(2, 1, body.length, rows[0].length).setValues(body);
  dateCols.forEach(function (c) { sh.getRange(2, c + 1, body.length).setNumberFormat('yyyy-mm'); });
  sh.setFrozenRows(1);
  return body.length;
}

function addBudgetVariance_(sh, n) {
  sh.getRange('E1:F1').setValues([['variance', 'variance_pct']]).setFontWeight('bold')
    .setBackground('#1F3864').setFontColor('#FFFFFF');
  const f = [];
  for (let r = 2; r <= n + 1; r++) f.push(['=C' + r + '-D' + r, '=IFERROR(E' + r + '/D' + r + ',0)']);
  sh.getRange(2, 5, n, 2).setFormulas(f);
  sh.getRange(2, 6, n).setNumberFormat('0.0%');
  const rng = sh.getRange(2, 6, n);
  sh.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=ABS($F2)>0.02')
      .setBackground('#F8CBAD').setRanges([rng]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=ABS($F2)<=0.02')
      .setBackground('#C6EFCE').setRanges([rng]).build(),
  ]);
}

function buildReport_(ss, n) {
  const sh = ss.getSheetByName('Report') || ss.insertSheet('Report');
  sh.clear();
  sh.getRange('A1').setValue('Membership Report - pick a product and month (yellow cells)')
    .setFontWeight('bold').setFontSize(14).setFontColor('#1F3864');
  const rows = [
    ['Product', ''],
    ['Month', ''],
    ['Members', '=SUMIFS(Data!$D:$D,Data!$B:$B,$B$3,Data!$A:$A,$B$4)'],
    ['Members, same month last year', '=SUMIFS(Data!$D:$D,Data!$B:$B,$B$3,Data!$A:$A,EDATE($B$4,-12))'],
    ['YoY change', '=B5-B6'],
    ['YoY %', '=IFERROR(B7/B6,"n/a")'],
    ['Gross adds', '=SUMIFS(Data!$E:$E,Data!$B:$B,$B$3,Data!$A:$A,$B$4)'],
    ['Terminations', '=SUMIFS(Data!$F:$F,Data!$B:$B,$B$3,Data!$A:$A,$B$4)'],
    ['Line of business (INDEX-MATCH)', '=INDEX(Products!$B:$B,MATCH($B$3,Products!$A:$A,0))'],
    ['Owner team (XLOOKUP)', '=XLOOKUP($B$3,Products!$A:$A,Products!$C:$C,"Not found")'],
    ['Owner team (VLOOKUP)', '=VLOOKUP($B$3,Products!$A:$C,3,FALSE)'],
    ['2026 budget', '=SUMIFS(Budget!$D:$D,Budget!$B:$B,$B$3,Budget!$A:$A,$B$4)'],
    ['Variance to budget %', '=IF(B14=0,"no budget",(B5-B14)/B14)'],
  ];
  rows.forEach(function (r, i) {
    sh.getRange(3 + i, 1).setValue(r[0]).setFontWeight('bold');
    if (r[1]) sh.getRange(3 + i, 2).setFormula(r[1]);
  });
  const products = ss.getSheetByName('Products');
  sh.getRange('B3').setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInRange(products.getRange(2, 1, products.getLastRow() - 1), true).setAllowInvalid(false).build())
    .setValue(products.getRange('A2').getValue());
  const months = ss.getSheetByName('Data').getRange(2, 1, n).getValues().map(function (r) { return r[0]; });
  const uniq = months.filter(function (d, i) {
    return months.findIndex(function (x) { return x.getTime() === d.getTime(); }) === i;
  }).sort(function (a, b) { return a - b; });
  const lists = ss.getSheetByName('Lists') || ss.insertSheet('Lists');
  lists.clear();
  lists.getRange(1, 1).setValue('month');
  lists.getRange(2, 1, uniq.length).setValues(uniq.map(function (d) { return [d]; })).setNumberFormat('mmm yyyy');
  lists.hideSheet();
  sh.getRange('B4').setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInRange(lists.getRange(2, 1, uniq.length), true).setAllowInvalid(false).build())
    .setValue(uniq[uniq.length - 1]).setNumberFormat('mmm yyyy');
  sh.getRange('B3:B4').setBackground('#FFF2CC');
  sh.getRangeList(['B5', 'B6', 'B7', 'B9', 'B10', 'B14']).setNumberFormat('#,##0');
  sh.getRangeList(['B8', 'B15']).setNumberFormat('0.0%');
  sh.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule().whenNumberLessThan(0).setBackground('#F8CBAD')
      .setRanges([sh.getRange('B8')]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=AND(ISNUMBER(B15),ABS(B15)>0.02)')
      .setBackground('#F8CBAD').setRanges([sh.getRange('B15')]).build(),
  ]);
  sh.setColumnWidth(1, 260);
  sh.setColumnWidth(2, 140);
}

function buildQuery_(ss) {
  const sh = ss.getSheetByName('Query') || ss.insertSheet('Query');
  sh.clear();
  sh.getRange('A1').setValue('QUERY: average monthly members by product, 2025 vs 2026 YTD').setFontWeight('bold');
  sh.getRange('A3').setFormula(
    '=QUERY(Data!A:J,"select B, avg(D) where J = 2025 group by B label avg(D) \'Avg members 2025\'",1)');
  sh.getRange('D3').setFormula(
    '=QUERY(Data!A:J,"select B, avg(D) where J = 2026 group by B label avg(D) \'Avg members 2026 YTD\'",1)');
  sh.getRange('B4:B10').setNumberFormat('#,##0');
  sh.getRange('E4:E10').setNumberFormat('#,##0');
}

function buildPivot_(ss, n) {
  const sh = ss.getSheetByName('Pivot') || ss.insertSheet('Pivot');
  sh.clear();
  sh.getRange('A1').setValue('Pivot table: average monthly members by product (rows) and year (columns)')
    .setFontWeight('bold');
  const src = ss.getSheetByName('Data').getRange(1, 1, n + 1, 10);
  const pt = sh.getRange('A3').createPivotTable(src);
  pt.addRowGroup(2);     // product
  pt.addColumnGroup(10); // year
  pt.addPivotValue(4, SpreadsheetApp.PivotTableSummarizeFunction.AVERAGE).setDisplayName('Avg monthly members');
}
