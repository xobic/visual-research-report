async page => {
  const baseUrl = __BASE_URL__;
  const artifactDir = __ARTIFACT_DIR__;
  const failures = [];
  const consoleErrors = [];
  let screenshots = 0;
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => consoleErrors.push(`pageerror: ${error.message}`));
  page.on('requestfailed', request => consoleErrors.push(`requestfailed: ${request.url()} ${request.failure()?.errorText || ''}`));
  const assert = (condition, message) => { if (!condition) failures.push(message); };
  const targets = [
    { name: 'site', path: 'site/index.html' },
    { name: 'single', path: 'report.html' },
  ];
  const viewports = [
    { name: 'desktop', width: 1440, height: 1000 },
    { name: 'tablet', width: 1024, height: 900 },
    { name: 'mobile', width: 390, height: 844 },
  ];

  for (const target of targets) {
    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto(`${baseUrl}/${target.path}`, { waitUntil: 'networkidle' });
      await page.waitForSelector('.report-section');
      await page.evaluate(() => document.fonts?.ready || Promise.resolve());
      await page.waitForTimeout(100);
      const label = `${target.name}/${viewport.name}`;

      await page.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-viewport.png` });
      screenshots += 1;
      const coverStage = page.locator('#cover-stage');
      await coverStage.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-cover.png` });
      screenshots += 1;
      const representative = page.locator('.chart-plate').first();
      await representative.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-chart.png` });
      screenshots += 1;
      const matrix = page.locator('[data-contained-overflow="true"]').first();
      if (await matrix.count()) {
        await matrix.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-matrix.png` });
        screenshots += 1;
      }

      const geometry = await page.evaluate(() => {
        const rail = document.querySelector('.research-rail');
        const firstSection = document.querySelector('.report-section');
        const touchSelectors = '.fact-chip,.cover-switcher button,.drawer-close,.rail-nav a,.flow-link,.pair-control,.pair-multiplier,.heat-cell,.odds-card,.entity-period,.line-mark,.balance-weight,.tripwire';
        const allowedOverflow = element => element.closest?.('.matrix-wrap,.line-wrap,.flow-grid');
        const escapedElements = [...document.querySelectorAll('body *')].filter(element => {
          if (allowedOverflow(element) || element.closest?.('[hidden]')) return false;
          const style = getComputedStyle(element);
          if (style.display === 'none' || style.visibility === 'hidden' || style.position === 'fixed') return false;
          const rect = element.getBoundingClientRect();
          return rect.width > 1 && (rect.left < -1 || rect.right > innerWidth + 1);
        }).slice(0, 8).map(element => `${element.tagName}.${String(element.className).slice(0, 40)}`);
        return {
          lang: document.documentElement.lang,
          preset: document.documentElement.dataset.designPreset,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          escapedElements,
          railTop: rail?.getBoundingClientRect().top ?? null,
          firstTop: firstSection?.getBoundingClientRect().top ?? null,
          railPosition: rail ? getComputedStyle(rail).position : null,
          coverTabs: document.querySelectorAll('[role="tab"]').length,
          chartCount: document.querySelectorAll('[data-chart-type]').length,
          disclosure: !!document.querySelector('.data-disclosure'),
          smallTargets: [...document.querySelectorAll(touchSelectors)].filter(element => {
            const rect = element.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0 && (rect.width + 0.5 < 40 || rect.height + 0.5 < 40);
          }).slice(0, 8).map(element => `${element.className}:${Math.round(element.getBoundingClientRect().width)}x${Math.round(element.getBoundingClientRect().height)}`),
          duplicateChartFacts: [...document.querySelectorAll('[data-chart-type]')].flatMap(chart => {
            const ids = [...chart.querySelectorAll('[data-fact-id]')].map(element => element.dataset.factId);
            return [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))].map(id => `${chart.id}:${id}`);
          }),
          stacks: [...document.querySelectorAll('.stack-ribbon')].map(ribbon => {
            const width = ribbon.getBoundingClientRect().width || 1;
            return [...ribbon.querySelectorAll('[data-stack-share]')].map(segment => ({ expected: Number(segment.dataset.stackShare), actual: segment.getBoundingClientRect().width / width * 100 }));
          }),
          lineColors: [...document.querySelectorAll('[data-chart-type="line"]')].map(chart => [...chart.querySelectorAll('.line-path')].map(path => getComputedStyle(path).getPropertyValue('--series-color').trim())),
          lineScroll: [...document.querySelectorAll('[data-scroll-latest="true"]')].map(wrap => ({ left: wrap.scrollLeft, max: wrap.scrollWidth - wrap.clientWidth })),
          matrixRegions: [...document.querySelectorAll('[data-contained-overflow="true"]')].map(wrap => ({
            contained: wrap.scrollWidth >= wrap.clientWidth,
            withinViewport: wrap.getBoundingClientRect().left >= -1 && wrap.getBoundingClientRect().right <= innerWidth + 1,
          })),
          sourceAnchors: [...document.querySelectorAll('.chart-source a')].every(anchor => !!document.querySelector(anchor.getAttribute('href'))),
        };
      });
      assert(geometry.lang.length > 0, `${label}: document language missing`);
      assert(['editorial-longform', 'institutional-rail'].includes(geometry.preset), `${label}: unknown design preset`);
      assert(geometry.overflow <= 1, `${label}: document overflows horizontally by ${geometry.overflow}px`);
      assert(geometry.escapedElements.length === 0, `${label}: elements escape viewport: ${geometry.escapedElements.join(', ')}`);
      assert(geometry.coverTabs === 4, `${label}: expected four cover tabs, found ${geometry.coverTabs}`);
      assert(geometry.chartCount > 0, `${label}: no charts rendered`);
      assert(geometry.disclosure, `${label}: synthetic disclosure missing`);
      assert(geometry.smallTargets.length === 0, `${label}: touch targets below 40px: ${geometry.smallTargets.join(', ')}`);
      assert(geometry.duplicateChartFacts.length === 0, `${label}: duplicate chart fact controls: ${geometry.duplicateChartFacts.join(', ')}`);
      assert(geometry.sourceAnchors, `${label}: chart source anchor does not resolve`);
      if (viewport.width < 1100) assert(geometry.railTop < geometry.firstTop, `${label}: directory/rail does not precede report body`);
      if (geometry.preset === 'editorial-longform' && viewport.width >= 1100) assert(geometry.railPosition !== 'sticky', `${label}: editorial directory must not be sticky`);
      geometry.matrixRegions.forEach((region, index) => {
        assert(region.contained, `${label}: matrix ${index} has invalid contained-overflow geometry`);
        assert(region.withinViewport, `${label}: matrix ${index} escapes the viewport`);
      });
      geometry.stacks.forEach((stack, index) => stack.forEach(segment => assert(Math.abs(segment.actual - segment.expected) < 0.25, `${label}: stack ${index} rendered width differs from declared share`)));
      geometry.lineColors.forEach((colors, index) => {
        const normalizedColors = colors.filter(Boolean).map(color => color.toLowerCase());
        assert(new Set(normalizedColors).size === normalizedColors.length, `${label}: line chart ${index} series colors are not unique`);
      });
      if (viewport.name === 'mobile') geometry.lineScroll.forEach((scroll, index) => assert(scroll.max <= 1 || scroll.left >= scroll.max - 2, `${label}: line ${index} is not positioned at latest observation`));

      const firstTab = page.locator('[role="tab"]').first();
      const initialMode = await coverStage.getAttribute('data-cover-mode');
      await firstTab.focus();
      await page.keyboard.press('ArrowRight');
      const activeTab = page.locator('[role="tab"][aria-selected="true"]');
      assert(await activeTab.getAttribute('tabindex') === '0', `${label}: cover roving tabindex failed`);
      assert(await coverStage.getAttribute('data-cover-mode') !== initialMode, `${label}: cover stage did not change with keyboard navigation`);

      const nav = page.locator('.rail-nav a').first();
      const href = await nav.getAttribute('href');
      await nav.click();
      assert((await page.evaluate(() => location.hash)) === href, `${label}: directory link did not update the anchor`);

      const trigger = page.locator('.kpi[data-fact-id],.fact-chip[data-fact-id],[data-chart-type] [data-fact-id]').first();
      await trigger.scrollIntoViewIfNeeded();
      await trigger.focus();
      const triggerFact = await trigger.getAttribute('data-fact-id');
      await trigger.click();
      const drawer = page.locator('#evidence-drawer');
      await drawer.waitFor({ state: 'visible' });
      if (viewport.name === 'mobile') {
        await drawer.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-drawer.png` });
        screenshots += 1;
      }
      const drawerState = await page.evaluate(() => {
        const drawerElement = document.getElementById('evidence-drawer');
        const rect = drawerElement.getBoundingClientRect();
        return {
          inert: document.getElementById('app').inert,
          rows: document.querySelectorAll('#drawer-content dt').length,
          sourceLinks: document.querySelectorAll('#drawer-content .drawer-sources a').length,
          focusInside: drawerElement.contains(document.activeElement),
          bottomSheet: innerWidth > 759 || (Math.abs(rect.bottom - innerHeight) <= 1 && rect.width >= innerWidth - 1),
        };
      });
      assert(drawerState.inert, `${label}: report is not inert while drawer is open`);
      assert(drawerState.rows >= 3, `${label}: evidence drawer lacks structured fields`);
      assert(drawerState.sourceLinks > 0, `${label}: evidence drawer lacks source link`);
      assert(drawerState.focusInside, `${label}: focus did not move into drawer`);
      assert(drawerState.bottomSheet, `${label}: mobile drawer is not a bottom sheet`);
      await page.locator('#drawer-close').focus();
      await page.keyboard.press('Shift+Tab');
      assert(await page.evaluate(() => document.getElementById('evidence-drawer').contains(document.activeElement)), `${label}: reverse focus trap failed`);
      await page.keyboard.press('Tab');
      assert(await page.evaluate(() => document.getElementById('evidence-drawer').contains(document.activeElement)), `${label}: forward focus trap failed`);
      await page.locator('#drawer-close').click();
      assert(await drawer.isHidden(), `${label}: explicit close did not close drawer`);
      assert(await page.evaluate(expected => document.activeElement?.dataset?.factId === expected, triggerFact), `${label}: explicit close did not return focus`);
      await trigger.click();
      await page.keyboard.press('Escape');
      assert(await drawer.isHidden(), `${label}: Escape did not close drawer`);
      await trigger.click();
      await page.locator('#drawer-scrim').click({ position: { x: 4, y: 4 } });
      assert(await drawer.isHidden(), `${label}: scrim did not close drawer`);
    }
  }
  assert(consoleErrors.length === 0, `browser errors: ${consoleErrors.join(' | ')}`);
  if (failures.length) throw new Error(`Visual Research Report browser QA failed:\n${failures.join('\n')}`);
  return { ok: true, checks: targets.length * viewports.length, screenshots };
}
