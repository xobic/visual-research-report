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
  const coverModes = ['recursive', 'exploded', 'blueprint', 'impact'];
  const waitForCoverReady = async label => {
    try {
      await page.waitForFunction(() => {
        const stage = document.getElementById('cover-stage');
        return stage?.dataset.coverReady === 'true' && stage.getAttribute('aria-busy') === 'false' && !stage.dataset.coverPending;
      }, null, { timeout: 15000 });
    } catch (_error) {
      assert(false, `${label}: cover image did not reach a decoded, non-busy state`);
    }
  };
  const readCoverState = () => page.evaluate(() => {
    const stage = document.getElementById('cover-stage');
    const visual = stage?.querySelector('[data-cover-visual].is-active');
    const image = visual?.querySelector('.cover-image');
    const src = image?.currentSrc || image?.src || '';
    let sourceHash = 2166136261;
    for (let index = 0; index < src.length; index += 1) {
      sourceHash ^= src.charCodeAt(index);
      sourceHash = Math.imul(sourceHash, 16777619);
    }
    const views = window.REPORT_DATA?.theme_atom?.views || [];
    const productionMode = window.REPORT_DATA?.theme_atom?.production?.mode || '';
    return {
      mode: stage?.dataset.coverMode || '',
      renderer: stage?.dataset.coverRenderer || '',
      ready: stage?.dataset.coverReady === 'true',
      busy: stage?.getAttribute('aria-busy') === 'true',
      activeVisuals: stage?.querySelectorAll('[data-cover-visual].is-active').length || 0,
      productionMode,
      assetMode: productionMode === 'image-2' || views.some(view => Boolean(view?.asset)),
      assetCount: views.filter(view => Boolean(view?.asset)).length,
      image: image ? {
        complete: image.complete,
        decoded: image.dataset.coverDecoded === 'true',
        naturalWidth: image.naturalWidth,
        naturalHeight: image.naturalHeight,
        sourceFingerprint: `${src.length}:${sourceHash >>> 0}`,
        objectFit: getComputedStyle(image).objectFit,
        objectPosition: getComputedStyle(image).objectPosition,
        declaredWidth: image.getAttribute('width') || '',
        declaredHeight: image.getAttribute('height') || '',
      } : null,
      schematicParts: visual?.querySelectorAll('.schematic-parts [data-part-id]').length || 0,
      coverAnimations: [...(visual?.querySelectorAll('.atom-part') || [])].map(part => getComputedStyle(part).animationName),
      coverTransitions: [...(stage?.querySelectorAll('[data-cover-visual],.cover-image') || [])].map(element => getComputedStyle(element).transitionDuration),
    };
  });
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
      const label = `${target.name}/${viewport.name}`;
      await waitForCoverReady(label);
      await page.waitForTimeout(100);

      await page.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-viewport.png` });
      screenshots += 1;
      const coverStage = page.locator('#cover-stage');
      await coverStage.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-cover.png` });
      screenshots += 1;
      const initialCover = await readCoverState();
      const representative = page.locator('.chart-plate').first();
      await representative.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-chart.png` });
      screenshots += 1;
      const historyPlate = page.locator('[data-chart-type="history-scrolly"]').first();
      if (await historyPlate.count()) {
        await historyPlate.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-history.png` });
        screenshots += 1;
      }
      const causalPlate = page.locator('[data-chart-type="causal-horizon-map"]').first();
      if (await causalPlate.count()) {
        await causalPlate.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-causal.png` });
        screenshots += 1;
      }
      const matrix = page.locator('[data-contained-overflow="true"]').first();
      if (await matrix.count()) {
        await matrix.screenshot({ path: `${artifactDir}/${target.name}-${viewport.name}-matrix.png` });
        screenshots += 1;
      }

      const geometry = await page.evaluate(() => {
        const rail = document.querySelector('.research-rail');
        const firstSection = document.querySelector('.report-section');
        const touchSelectors = '.fact-chip,.cover-switcher button,.drawer-close,.rail-nav a,.flow-link,.pair-control,.pair-multiplier,.heat-cell,.odds-card,.entity-period,.line-mark,.balance-weight,.tripwire,.history-mark,.history-scene-trigger,.history-annotation-fact,.causal-fact,.causal-sparkline-mark';
        const allowedOverflow = element => element.closest?.('.matrix-wrap,.line-wrap,.flow-grid,.history-stage,.causal-horizon-map,.rail-nav');
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
          railTopCss: rail ? getComputedStyle(rail).top : null,
          railNavScroll: document.querySelector('.rail-nav') ? {
            width: document.querySelector('.rail-nav').clientWidth,
            scrollWidth: document.querySelector('.rail-nav').scrollWidth,
          } : null,
          coverTabs: document.querySelectorAll('[role="tab"]').length,
          schematicParts: document.querySelectorAll('#cover-stage .schematic-parts [data-part-id]').length,
          coverAnimations: [...document.querySelectorAll('#cover-stage .atom-part')].map(part => getComputedStyle(part).animationName),
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
          histories: [...document.querySelectorAll('[data-history-scrolly]')].map(root => {
            const chart = root.querySelector('.history-chart');
            return {
              mode: root.dataset.historyMode,
              scenes: root.querySelectorAll('[data-scrolly-step]').length,
              activeScenes: root.querySelectorAll('[data-scrolly-step][aria-current="true"]').length,
              focusStart: chart?.dataset.focusStart || '',
              focusEnd: chart?.dataset.focusEnd || '',
            };
          }),
          causalNodes: [...document.querySelectorAll('.causal-node[data-node-id]')].map(node => ({
            id: node.dataset.nodeId,
            direction: node.dataset.direction,
            confidence: node.dataset.confidence,
            sparkline: !!node.querySelector('.causal-sparkline'),
          })),
        };
      });
      assert(geometry.lang.length > 0, `${label}: document language missing`);
      assert(['editorial-longform', 'editorial-scrollspy', 'institutional-rail'].includes(geometry.preset), `${label}: unknown design preset`);
      assert(geometry.overflow <= 1, `${label}: document overflows horizontally by ${geometry.overflow}px`);
      assert(geometry.escapedElements.length === 0, `${label}: elements escape viewport: ${geometry.escapedElements.join(', ')}`);
      assert(geometry.coverTabs === 4, `${label}: expected four cover tabs, found ${geometry.coverTabs}`);
      assert(initialCover.ready && !initialCover.busy, `${label}: cover remained busy after readiness wait`);
      assert(initialCover.activeVisuals === 1, `${label}: cover must expose exactly one active visual`);
      assert(initialCover.coverTransitions.every(duration => duration.split(',').every(value => Number.parseFloat(value) === 0)), `${label}: cover transition remains active under reduced motion`);
      if (initialCover.assetMode) {
        assert(initialCover.assetCount === 4, `${label}: Image-2/asset cover requires four assets, found ${initialCover.assetCount}`);
        assert(initialCover.renderer === 'asset', `${label}: declared asset cover rendered as ${initialCover.renderer || 'unknown'}`);
        assert(initialCover.image?.complete && initialCover.image?.decoded, `${label}: active cover image was not loaded and decoded`);
        assert(initialCover.image?.naturalWidth > 0 && initialCover.image?.naturalHeight > 0, `${label}: active cover image has empty intrinsic dimensions`);
        assert(['cover', 'contain', 'scale-down'].includes(initialCover.image?.objectFit), `${label}: cover image has invalid object-fit`);
        assert(Boolean(initialCover.image?.objectPosition), `${label}: cover image has no focal/object position`);
      } else {
        assert(initialCover.renderer === 'schematic' || initialCover.renderer === 'fallback', `${label}: schematic cover renderer marker is missing`);
        assert(initialCover.schematicParts >= 2, `${label}: engineering cover schematic did not render`);
        assert(initialCover.coverAnimations.every(name => name === 'none'), `${label}: cover animation remains active under reduced motion`);
      }
      assert(geometry.chartCount > 0, `${label}: no charts rendered`);
      assert(geometry.disclosure, `${label}: synthetic disclosure missing`);
      assert(geometry.smallTargets.length === 0, `${label}: touch targets below 40px: ${geometry.smallTargets.join(', ')}`);
      assert(geometry.duplicateChartFacts.length === 0, `${label}: duplicate chart fact controls: ${geometry.duplicateChartFacts.join(', ')}`);
      assert(geometry.sourceAnchors, `${label}: chart source anchor does not resolve`);
      if (viewport.width < 1100 && geometry.preset !== 'editorial-scrollspy') assert(geometry.railTop < geometry.firstTop, `${label}: directory/rail does not precede report body`);
      if (geometry.preset === 'editorial-longform' && viewport.width >= 1100) assert(geometry.railPosition !== 'sticky', `${label}: editorial directory must not be sticky`);
      if (geometry.preset === 'editorial-scrollspy') {
        assert(geometry.railPosition === 'sticky', `${label}: editorial chapter track is not sticky`);
        assert(geometry.railTopCss === '0px', `${label}: editorial chapter track does not pin to the viewport top`);
        assert(geometry.railNavScroll && geometry.railNavScroll.scrollWidth >= geometry.railNavScroll.width, `${label}: chapter track scroll geometry is invalid`);
      }
      assert(geometry.histories.length > 0, `${label}: history-scrolly did not render`);
      geometry.histories.forEach((history, index) => {
        assert(history.mode === 'static', `${label}: history ${index} did not enter reduced-motion static mode`);
        assert(history.scenes >= 2, `${label}: history ${index} lacks ordered scenes`);
        assert(history.activeScenes === 1, `${label}: history ${index} must expose exactly one current scene`);
        assert(history.focusStart && history.focusEnd, `${label}: history ${index} lacks a focus domain`);
      });
      assert(geometry.causalNodes.length >= 2, `${label}: causal horizon nodes did not render`);
      geometry.causalNodes.forEach((node, index) => {
        assert(['up', 'down', 'mixed'].includes(node.direction), `${label}: causal node ${index} lacks textual direction`);
        assert(['low', 'medium', 'high'].includes(node.confidence), `${label}: causal node ${index} lacks textual confidence`);
        assert(node.sparkline, `${label}: causal node ${index} lacks a sparkline`);
      });
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
      const initialPartCount = initialCover.schematicParts;
      await firstTab.focus();
      await page.keyboard.press('ArrowRight');
      await waitForCoverReady(`${label}/keyboard`);
      const activeTab = page.locator('[role="tab"][aria-selected="true"]');
      const keyboardCover = await readCoverState();
      assert(await activeTab.getAttribute('tabindex') === '0', `${label}: cover roving tabindex failed`);
      assert(await coverStage.getAttribute('data-cover-mode') !== initialMode, `${label}: cover stage did not change with keyboard navigation`);
      if (initialCover.assetMode) {
        assert(keyboardCover.renderer === 'asset' && keyboardCover.image?.decoded, `${label}: keyboard-selected cover asset did not decode`);
        assert(keyboardCover.image?.sourceFingerprint !== initialCover.image?.sourceFingerprint, `${label}: adjacent cover tabs reused the same asset`);
      } else {
        assert(await coverStage.locator('.schematic-parts [data-part-id]').count() === initialPartCount, `${label}: cover mode changed the physical schematic parts`);
      }

      if (viewport.name === 'desktop') {
        const fingerprints = [];
        for (const mode of coverModes) {
          await page.locator(`[data-cover-view="${mode}"]`).click();
          await waitForCoverReady(`${label}/${mode}/reduced`);
          const state = await readCoverState();
          assert(state.mode === mode && state.activeVisuals === 1, `${label}: ${mode} did not become the sole active cover state`);
          if (state.assetMode) {
            assert(state.renderer === 'asset' && state.image?.decoded && state.image?.naturalWidth > 0, `${label}: ${mode} asset did not load`);
            fingerprints.push(state.image?.sourceFingerprint);
          } else {
            assert(state.schematicParts === initialPartCount, `${label}: ${mode} changed the physical schematic parts`);
          }
          await coverStage.screenshot({ path: `${artifactDir}/${target.name}-desktop-cover-${mode}-reduced.png` });
          screenshots += 1;
        }
        if (initialCover.assetMode) assert(new Set(fingerprints).size === 4, `${label}: the four cover states do not use four unique loaded assets`);
      }

      const nav = page.locator('.rail-nav a').first();
      const href = await nav.getAttribute('href');
      await nav.click();
      assert((await page.evaluate(() => location.hash)) === href, `${label}: directory link did not update the anchor`);
      if (geometry.preset === 'editorial-scrollspy') {
        await page.waitForTimeout(120);
        assert(await nav.evaluate(element => element.classList.contains('is-active')), `${label}: chapter scrollspy did not activate the selected section`);
      }

      const trigger = page.locator('.kpi[data-fact-id]:visible,.fact-chip[data-fact-id]:visible,[data-chart-type] [data-fact-id]:visible').first();
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

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  for (const target of targets) {
    const label = `${target.name}/desktop/motion`;
    await page.goto(`${baseUrl}/${target.path}`, { waitUntil: 'networkidle' });
    await page.waitForSelector('#cover-stage [data-cover-visual]');
    await waitForCoverReady(label);
    const fingerprints = [];
    let assetMode = false;
    for (const mode of coverModes) {
      await page.locator(`[data-cover-view="${mode}"]`).click();
      await waitForCoverReady(`${label}/${mode}`);
      const state = await readCoverState();
      assetMode = state.assetMode;
      assert(state.mode === mode && state.activeVisuals === 1, `${label}: ${mode} did not settle before capture`);
      if (state.assetMode) {
        assert(state.renderer === 'asset' && state.image?.decoded && state.image?.naturalWidth > 0, `${label}: ${mode} asset did not decode before capture`);
        fingerprints.push(state.image?.sourceFingerprint);
      } else {
        assert(state.renderer === 'schematic' || state.renderer === 'fallback', `${label}: ${mode} lacks a renderer marker`);
        assert(state.schematicParts >= 2, `${label}: ${mode} schematic parts are missing`);
      }
      await page.waitForTimeout(state.assetMode ? 80 : (mode === 'recursive' ? 650 : mode === 'exploded' ? 900 : 520));
      await page.locator('#cover-stage').screenshot({ path: `${artifactDir}/${target.name}-desktop-cover-${mode}-motion.png` });
      screenshots += 1;
    }
    if (assetMode) assert(new Set(fingerprints).size === 4, `${label}: the four motion captures do not use four unique loaded assets`);
  }
  assert(consoleErrors.length === 0, `browser errors: ${consoleErrors.join(' | ')}`);
  if (failures.length) throw new Error(`Visual Research Report browser QA failed:\n${failures.join('\n')}`);
  return { ok: true, checks: targets.length * viewports.length, screenshots };
}
