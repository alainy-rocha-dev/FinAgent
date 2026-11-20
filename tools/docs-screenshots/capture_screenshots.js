const { chromium } = require('playwright');

(async () => {
    console.log('Acessando servidor HTTP local http://localhost:8085...');
    const browser = await chromium.launch({ headless: true });
    // Viewport 1280x800 (proporção 16:10 ideal para visualização de dashboards e 3D)
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

    // 0. Screenshot do Index / Capa (index.html)
    console.log('Capturando Capa (index.html)...');
    await page.goto('http://localhost:8085/index.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: '_reversa_docs/screenshot_index.png' });

    // 1. Screenshot da Cidade 3D (arquitetura.html)
    console.log('Capturando Cidade 3D...');
    await page.goto('http://localhost:8085/arquitetura.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(4000); // aguarda carregamento das bibliotecas 3D
    await page.screenshot({ path: '_reversa_docs/screenshot_3d.png' });

    // 2. Screenshot do Grafo 2D (modulos.html)
    console.log('Capturando Grafo 2D...');
    await page.goto('http://localhost:8085/modulos.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '_reversa_docs/screenshot_2d.png' });

    // 3. Screenshot de Métricas (metricas.html)
    console.log('Capturando Métricas...');
    await page.goto('http://localhost:8085/metricas.html', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '_reversa_docs/screenshot_metricas.png' });

    await browser.close();
    console.log('Todas as capturas foram concluídas com sucesso!');
})();
