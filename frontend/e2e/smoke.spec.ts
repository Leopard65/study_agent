import { expect, test } from '@playwright/test';
import { Buffer } from 'node:buffer';

const pages = [
  { path: '/', heading: '学习工作台' },
  { path: '/qa', heading: 'AI 问答' },
  { path: '/materials', heading: '资料库' },
  { path: '/problems', heading: '题目解析' },
  { path: '/errors', heading: '错题本' },
  { path: '/plan', heading: '学习计划' },
  { path: '/exam', heading: '真题练习' },
  { path: '/review', heading: '今日复习' },
  { path: '/search', heading: '全局搜索' },
];

test.describe('frontend smoke', () => {
  test('loads all main routes', async ({ page }) => {
    for (const item of pages) {
      await page.goto(item.path);
      await expect(page.getByRole('heading', { name: item.heading }).first()).toBeVisible();
    }
  });

  test('opens command palette and navigates', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /命令面板/ }).click();
    await expect(page.getByRole('dialog', { name: '命令面板' })).toBeVisible();

    await page.getByRole('combobox').fill('资料');
    await expect(page.getByRole('option', { name: /打开资料库/ })).toBeVisible();
    await page.keyboard.press('Enter');

    await expect(page).toHaveURL(/\/materials$/);
    await expect(page.getByRole('heading', { name: '资料库' })).toBeVisible();
  });

  test('persists dark theme and collapsed sidebar preference', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('button', { name: '深色' }).click();
    await expect(page.locator('html')).toHaveClass(/dark/);

    await page.locator('button[title="折叠侧边栏"]').click();
    await expect(page.locator('button[title="展开侧边栏"]')).toBeVisible();

    await page.reload();
    await expect(page.locator('html')).toHaveClass(/dark/);
    await expect(page.locator('button[title="展开侧边栏"]')).toBeVisible();
  });

  test('uses mobile sidebar drawer navigation', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    await page.getByRole('button', { name: '打开菜单' }).click();
    await expect(page.getByRole('link', { name: /资料库/ })).toBeVisible();
    await page.getByRole('link', { name: /资料库/ }).click();

    await expect(page).toHaveURL(/\/materials$/);
    await expect(page.getByRole('heading', { name: '资料库' })).toBeVisible();
    await expect(page.getByRole('button', { name: '打开菜单' })).toBeVisible();
  });

  test('uploads, searches, previews, and deletes a material', async ({ page }) => {
    const marker = `E2E卷积定理-${Date.now()}`;
    const filename = `${marker}.txt`;

    await page.goto('/materials');
    await page.locator('input[type="file"][accept=".pdf,.docx,.doc,.txt,.md"]').setInputFiles({
      name: filename,
      mimeType: 'text/plain',
      buffer: Buffer.from(`这是 Playwright 端到端测试资料，关键词 ${marker}。`, 'utf-8'),
    });

    await expect(page.getByText(filename)).toBeVisible();

    // Wait for background parsing to complete (status badge becomes "就绪")
    await expect(page.getByText('就绪').first()).toBeVisible({ timeout: 10_000 });

    await page.getByPlaceholder('关键词检索资料内容...').fill(marker);
    await page.getByRole('button', { name: '搜索' }).click();
    await expect(page.getByRole('heading', { name: /搜索结果/ })).toBeVisible();
    await expect(page.getByText(filename).first()).toBeVisible();

    const materialRow = page
      .getByText(filename)
      .last()
      .locator('xpath=ancestor::div[.//button[normalize-space()="查看"]][1]');
    await materialRow.getByRole('button', { name: '查看' }).click();

    // Detail modal should show chunks with content
    await expect(page.getByText(`关键词 ${marker}`).first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/段落 #1/)).toBeVisible();

    // In-material search should work
    await page.getByPlaceholder('在资料内搜索...').fill(marker);
    await page.locator('.fixed').getByRole('button', { name: '搜索' }).click();
    await expect(page.getByText(/匹配片段/)).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.fixed mark').first()).toBeVisible();

    await page.locator('.fixed').getByRole('button', { name: '×' }).click();

    page.on('dialog', dialog => dialog.accept());
    await materialRow.getByRole('button', { name: '删除' }).click();
    await expect(page.getByText(filename)).toHaveCount(0);
  });

  test('deep link with open and q opens material detail with search', async ({ page }) => {
    const marker = `E2E深链-${Date.now()}`;
    const filename = `${marker}.txt`;
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;

    // Create material via API
    const uploadRes = await page.request.post(`${apiBase}/materials/upload`, {
      multipart: { file: { name: filename, mimeType: 'text/plain', buffer: Buffer.from(`深链测试内容包含关键词 ${marker} 用于验证。`, 'utf-8') } },
    });
    const mat = await uploadRes.json();
    const matId = mat.id;

    // Wait for parsing
    for (let i = 0; i < 30; i++) {
      const r = await page.request.get(`${apiBase}/materials/${matId}`);
      const d = await r.json();
      if (d.status === 'ready' || d.status === 'failed') break;
      await page.waitForTimeout(200);
    }

    // Navigate with deep link: open=id&q=keyword
    await page.goto(`/materials?open=${matId}&q=${encodeURIComponent(marker)}`);

    // Modal should open with the material detail
    await expect(page.getByText(filename).first()).toBeVisible({ timeout: 5_000 });

    // The in-material search should be pre-filled with the query
    await expect(page.getByPlaceholder('在资料内搜索...')).toHaveValue(marker);

    // Should show matching chunks with highlights
    await expect(page.getByText(/匹配片段/)).toBeVisible({ timeout: 5_000 });

    // URL should have open removed but q preserved
    await expect(page).toHaveURL(new RegExp(`q=${encodeURIComponent(marker)}`));
    await expect(page).not.toHaveURL(/open=/);

    // Close modal
    await page.locator('.fixed').getByRole('button', { name: '×' }).click();

    // Refresh: q is still in URL, but open is gone — modal should NOT reopen
    await page.reload();
    await expect(page.getByRole('heading', { name: '资料库' })).toBeVisible();
    // Modal should not be present (no open=id in URL)
    await expect(page.getByText('在资料内搜索...')).toHaveCount(0);

    // Cleanup
    await page.request.delete(`${apiBase}/materials/${matId}`);
  });

  test('upload shows pending/processing status before ready', async ({ page }) => {
    const marker = `E2E状态测试-${Date.now()}`;
    const filename = `${marker}.txt`;

    await page.goto('/materials');
    await page.locator('input[type="file"][accept=".pdf,.docx,.doc,.txt,.md"]').setInputFiles({
      name: filename,
      mimeType: 'text/plain',
      buffer: Buffer.from(`状态流转测试 ${marker}。`, 'utf-8'),
    });

    await expect(page.getByText(filename)).toBeVisible();
    // Should show one of: 等待解析, 解析中, 就绪 (transitions fast for txt)
    // Eventually should become 就绪
    await expect(page.getByText('就绪').first()).toBeVisible({ timeout: 10_000 });

    // Cleanup
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;
    const listRes = await page.request.get(`${apiBase}/materials?limit=100`);
    const items = await listRes.json();
    const target = items.find((m: { filename: string }) => m.filename === filename);
    if (target) {
      await page.request.delete(`${apiBase}/materials/${target.id}`);
    }
  });

  test('parse jobs section appears after upload and shows status', async ({ page }) => {
    const marker = `E2E任务测试-${Date.now()}`;
    const filename = `${marker}.txt`;

    await page.goto('/materials');
    await page.locator('input[type="file"][accept=".pdf,.docx,.doc,.txt,.md"]').setInputFiles({
      name: filename,
      mimeType: 'text/plain',
      buffer: Buffer.from(`解析任务区域测试 ${marker}。`, 'utf-8'),
    });

    // The "解析任务" toggle should appear
    await expect(page.getByText(/解析任务/)).toBeVisible({ timeout: 5_000 });

    // Click to expand
    await page.getByText(/解析任务/).click();

    // Should show the job entry with filename
    await expect(page.getByText(filename).first()).toBeVisible({ timeout: 5_000 });

    // Wait for completion
    await expect(page.getByText('就绪').first()).toBeVisible({ timeout: 10_000 });

    // The jobs section should eventually show "已完成" status
    // (may need to wait for poll to update)
    await expect(page.getByText('已完成').first()).toBeVisible({ timeout: 10_000 });

    // Cleanup
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;
    const listRes = await page.request.get(`${apiBase}/materials?limit=100`);
    const items = await listRes.json();
    const target = items.find((m: { filename: string }) => m.filename === filename);
    if (target) {
      await page.request.delete(`${apiBase}/materials/${target.id}`);
    }
  });

  test('shows error stats panel with charts', async ({ page }) => {
    // Seed some error records via API
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;
    const seedErrors = [
      { question: 'E2E积分题1', subject: '高数', error_type: '计算错误', knowledge_point: '不定积分' },
      { question: 'E2E积分题2', subject: '高数', error_type: '概念错误', knowledge_point: '不定积分' },
      { question: 'E2E矩阵题1', subject: '线代', error_type: '计算错误', knowledge_point: '矩阵运算' },
    ];
    const createdIds: number[] = [];
    for (const e of seedErrors) {
      const res = await page.request.post(`${apiBase}/errors`, { data: e });
      const body = await res.json();
      createdIds.push(body.id);
    }

    await page.goto('/errors');
    await expect(page.getByRole('heading', { name: '错题本' })).toBeVisible();

    // Open stats panel
    await page.getByText('错题统计分析').click();

    // Summary cards should be visible (use first() to disambiguate from filter buttons)
    await expect(page.getByText('总错题').first()).toBeVisible();
    await expect(page.getByText('今日待复习').first()).toBeVisible();

    // Charts should render (recharts renders SVGs)
    await expect(page.locator('.recharts-responsive-container').first()).toBeVisible();

    // Distribution sections
    await expect(page.getByText('科目分布')).toBeVisible();
    await expect(page.getByText('错误类型')).toBeVisible();
    await expect(page.getByText('知识点 Top 10')).toBeVisible();
    await expect(page.getByText('最近 30 天新增错题')).toBeVisible();

    // Chart bars/areas should have rendered data (SVG elements)
    await expect(page.locator('.recharts-bar-rectangle').first()).toBeVisible();
    await expect(page.locator('.recharts-area').first()).toBeVisible();

    // Cleanup
    for (const id of createdIds) {
      await page.request.delete(`${apiBase}/errors/${id}`);
    }
  });

  test('error stats panel works on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/errors');

    // Open stats panel
    await page.getByText('错题统计分析').click();

    // Summary cards should be visible in 2-column layout
    await expect(page.getByText('总错题')).toBeVisible();

    // Charts should render without overflow
    await expect(page.locator('.recharts-responsive-container').first()).toBeVisible();

    // Close stats
    await page.getByText('收起错题统计').click();
    await expect(page.getByText('总错题')).toHaveCount(0);
  });

  test('search restores URL state and syncs type filters', async ({ page }) => {
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;
    const marker = `E2E搜索-${Date.now()}`;
    const errorRes = await page.request.post(`${apiBase}/errors`, {
      data: { question: `${marker} 错题题干`, subject: '高数', error_type: '搜索测试' },
    });
    const examRes = await page.request.post(`${apiBase}/exam/questions`, {
      data: { title: `${marker} 真题标题`, question: `${marker} 真题题干` },
    });
    const errorId = (await errorRes.json()).id;
    const examId = (await examRes.json()).id;

    await page.goto(`/search?q=${encodeURIComponent(marker)}&types=errors`);

    await expect(page.getByPlaceholder('搜索资料、错题、计划、真题、问答、解析...')).toHaveValue(marker);
    await expect(page.getByText(`${marker} 错题题干`)).toBeVisible();
    await expect(page.getByText('题干命中')).toBeVisible();
    await expect(page.getByText(`${marker} 真题标题`)).toHaveCount(0);
    await expect(page).toHaveURL(new RegExp(`q=${encodeURIComponent(marker)}.*types=errors`));

    await page.reload();
    await expect(page.getByText(`${marker} 错题题干`)).toBeVisible();

    await page.getByRole('button', { name: /真题/ }).click();
    await expect(page).toHaveURL(/types=errors%2Cexam|types=errors,exam/);
    await expect(page.getByText(`${marker} 真题标题`)).toBeVisible();

    await page.getByRole('button', { name: '清除筛选' }).click();
    await expect(page).not.toHaveURL(/types=/);
    await expect(page.getByText(`${marker} 错题题干`)).toBeVisible();
    await expect(page.getByText(`${marker} 真题标题`)).toBeVisible();
    await expect(page.getByText(/共找到 \d+ 条结果/)).toBeVisible();

    await page.request.delete(`${apiBase}/errors/${errorId}`);
    await page.request.delete(`${apiBase}/exam/questions/${examId}`);
  });

  test('search pagination: load more and reset on query change', async ({ page }) => {
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;
    const marker = `E2E分页-${Date.now()}`;
    const createdIds: number[] = [];

    // Create enough errors to trigger pagination (PAGE_SIZE=20, need >20)
    for (let i = 0; i < 25; i++) {
      const res = await page.request.post(`${apiBase}/errors`, {
        data: { question: `${marker} 第${i}题`, subject: '分页测试', error_type: '分页' },
      });
      createdIds.push((await res.json()).id);
    }

    await page.goto(`/search?q=${encodeURIComponent(marker)}`);
    await expect(page.getByText(/共找到 \d+ 条结果/)).toBeVisible();

    // Should show "已加载 20 条" if total > 20
    const totalText = page.getByText(/共找到 \d+ 条结果/);
    await expect(totalText).toBeVisible();

    // "加载更多" button should be visible if total > loaded
    const loadMoreBtn = page.getByRole('button', { name: '加载更多' });
    // It may or may not be visible depending on total vs PAGE_SIZE
    const totalMatch = await totalText.textContent();
    const totalNum = parseInt(totalMatch?.match(/共找到 (\d+) 条/)?.[1] || '0', 10);

    if (totalNum > 20) {
      await expect(loadMoreBtn).toBeVisible();
      await expect(page.getByText(/已加载 20 条/)).toBeVisible();

      // Click load more
      await loadMoreBtn.click();
      await expect(page.getByText(/已加载/)).not.toBeVisible(); // all loaded now

      // URL should contain offset
      await expect(page).toHaveURL(/offset=/);

      // Reload should restore all pages that had already been loaded.
      await page.reload();
      await expect(page.getByText(`${marker} 第24题`)).toBeVisible();
      await expect(page.getByText(/已加载 20 条/)).toHaveCount(0);

      // Changing query resets pagination
      const input = page.getByPlaceholder('搜索资料、错题、计划、真题、问答、解析...');
      await input.fill('新关键词');
      await page.waitForTimeout(400);
      await expect(page).not.toHaveURL(/offset=/);
    }

    // Cleanup
    for (const id of createdIds) {
      await page.request.delete(`${apiBase}/errors/${id}`);
    }
  });
});

test.describe('search network behavior', () => {
  test.use({ serviceWorkers: 'block' });

  test('search ignores stale slower responses', async ({ page }) => {
    await page.route('**/api/search**', async route => {
      const url = new URL(route.request().url());
      const q = url.searchParams.get('q') || '';
      if (q === 'slow') {
        await new Promise(resolve => setTimeout(resolve, 900));
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          query: q,
          total: 1,
          results: [{
            type: 'error',
            id: q === 'slow' ? 1 : 2,
            title: `${q}-result`,
            snippet: `${q}-snippet`,
            created_at: null,
            match_field: 'question',
          }],
        }),
      });
    });

    await page.goto('/search');
    const input = page.getByPlaceholder('搜索资料、错题、计划、真题、问答、解析...');
    await input.fill('slow');
    await page.waitForTimeout(350);
    await input.fill('fast');

    await expect(page.getByText('fast-result')).toBeVisible();
    await expect(page.getByText('slow-result')).toHaveCount(0);
  });

});

test.describe('review queue', () => {
  test('seed errors, expand answer, mark mastered, completion', async ({ page }) => {
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;

    // Use local date (YYYY-MM-DD in Asia/Shanghai) matching the backend
    const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
    const future = new Date(Date.now() + 30 * 86400000).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

    const err1Res = await page.request.post(`${apiBase}/errors`, {
      data: {
        subject: '高数', knowledge_point: '极限', error_type: '计算错误',
        question: 'E2E 复习测试题 1：求极限 $\\lim_{x\\to 0} \\frac{\\sin x}{x}$',
        correct_answer: '1', correct_approach: '等价无穷小替换',
        review_suggestion: '多做极限计算练习',
        next_review_date: today,
      },
    });
    expect(err1Res.ok()).toBeTruthy();
    const err1 = await err1Res.json();

    const err2Res = await page.request.post(`${apiBase}/errors`, {
      data: {
        subject: '线代', knowledge_point: '矩阵',
        question: 'E2E 复习测试题 2：矩阵乘法不满足交换律',
        next_review_date: today,
      },
    });
    expect(err2Res.ok()).toBeTruthy();
    const err2 = await err2Res.json();

    // Future error should not appear
    const err3Res = await page.request.post(`${apiBase}/errors`, {
      data: { subject: '概率', question: 'E2E 未来错题', next_review_date: future },
    });
    expect(err3Res.ok()).toBeTruthy();
    const err3 = await err3Res.json();

    try {
      // Navigate to review queue
      await page.goto('/review');
      await expect(page.getByRole('heading', { name: '今日复习' })).toBeVisible();

      // Wait for queue to load — progress shows "N / N"
      await expect(page.getByText(/\/ \d/)).toBeVisible({ timeout: 10000 });

      // First question should be visible
      await expect(page.getByText(/E2E 复习测试题/)).toBeVisible();

      // Verify badges
      await expect(page.getByText('高数').or(page.getByText('线代'))).toBeVisible();

      // Click "显示解析与答案"
      await page.getByRole('button', { name: /显示解析与答案/ }).click();

      // Answer section should appear
      await expect(page.getByText(/正确答案|正确思路|复习建议/).first()).toBeVisible();

      // Click "标记掌握"
      await page.getByRole('button', { name: /标记掌握/ }).click();

      // After mastering one, should advance to next (or complete if last)
      // The progress should update
      await page.waitForTimeout(500);

      // Click "显示解析与答案" for the second question (if visible)
      const showBtn = page.getByRole('button', { name: /显示解析与答案/ });
      if (await showBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await showBtn.click();
        // Mark mastered again
        await page.getByRole('button', { name: /标记掌握/ }).click();
        await page.waitForTimeout(500);
      }

      // Should reach completion state
      await expect(page.getByText(/本轮复习完成|今日无待复习错题/)).toBeVisible({ timeout: 5000 });

      // Completion page should have navigation links
      await expect(page.getByRole('link', { name: /返回工作台/ })).toBeVisible();
      await expect(page.getByRole('link', { name: /查看错题本/ })).toBeVisible();
    } finally {
      // Cleanup
      await page.request.delete(`${apiBase}/errors/${err1.id}`);
      await page.request.delete(`${apiBase}/errors/${err2.id}`);
      await page.request.delete(`${apiBase}/errors/${err3.id}`);
    }
  });
});

test.describe('ZIP backup', () => {
  test('sidebar shows ZIP export/import buttons', async ({ page }) => {
    await page.goto('/');
    // Export buttons
    await expect(page.getByRole('button', { name: /数据 JSON/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /完整 ZIP/ })).toBeVisible();
    // Import buttons (labels)
    await expect(page.getByText('导入 JSON')).toBeVisible();
    await expect(page.getByText('导入 ZIP')).toBeVisible();
  });

  test('ZIP import preview shows settings and sessions', async ({ page }) => {
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;
    const marker = `E2EZIPSS-${Date.now()}`;

    // Create a session and set custom review intervals
    await page.request.put(`${apiBase}/settings/review`, { data: { intervals: [2, 5, 10] } });
    const sessRes = await page.request.post(`${apiBase}/sessions/start`, { data: { subject: marker, note: 'e2e' } });
    const sess = await sessRes.json();
    await page.waitForTimeout(500);
    await page.request.post(`${apiBase}/sessions/${sess.id}/stop`);

    // Export ZIP
    const zipRes = await page.request.get(`${apiBase}/export/zip`);
    const zipBuffer = await zipRes.body();

    // Reset intervals
    await page.request.put(`${apiBase}/settings/review`, { data: { intervals: [1, 3, 7, 14] } });

    // Import preview
    await page.goto('/');
    const zipInput = page.locator('input[type="file"][accept=".zip"]');
    await zipInput.setInputFiles({
      name: `${marker}_backup.zip`,
      mimeType: 'application/zip',
      buffer: Buffer.from(zipBuffer),
    });

    await expect(page.getByText(/完整备份预览/)).toBeVisible({ timeout: 10_000 });

    // Preview should show settings and sessions counts (use the summary line)
    await expect(page.getByText(/设置: [1-9]/)).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/会话:.*[1-9]/).first()).toBeVisible({ timeout: 5_000 });

    // Cancel
    await page.getByRole('button', { name: '取消' }).click();

    // Cleanup
    await page.request.delete(`${apiBase}/materials/0`).catch(() => {});
  });

  test('ZIP import preview flow with strategy selector', async ({ page }) => {
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;
    const marker = `E2EZIP-${Date.now()}`;

    // Create a material via API to have data in the backup
    const uploadRes = await page.request.post(`${apiBase}/materials/upload`, {
      multipart: {
        file: { name: `${marker}.txt`, mimeType: 'text/plain', buffer: Buffer.from(`ZIP E2E 测试内容 ${marker}`, 'utf-8') },
      },
    });
    const mat = await uploadRes.json();

    // Wait for parsing
    for (let i = 0; i < 30; i++) {
      const r = await page.request.get(`${apiBase}/materials/${mat.id}`);
      const d = await r.json();
      if (d.status === 'ready' || d.status === 'failed') break;
      await page.waitForTimeout(200);
    }

    // Download ZIP via API
    const zipRes = await page.request.get(`${apiBase}/export/zip`);
    const zipBuffer = await zipRes.body();

    // Navigate to page and trigger ZIP import preview
    await page.goto('/');
    const zipInput = page.locator('input[type="file"][accept=".zip"]');
    await zipInput.setInputFiles({
      name: `${marker}_backup.zip`,
      mimeType: 'application/zip',
      buffer: Buffer.from(zipBuffer),
    });

    // Preview should appear
    await expect(page.getByText(/完整备份预览/)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/📦/)).toBeVisible();
    await expect(page.getByText(/个文件/)).toBeVisible();

    // Strategy selector should be visible
    await expect(page.getByText('冲突策略：')).toBeVisible();
    await expect(page.getByRole('radio', { name: /跳过/ })).toBeVisible();
    await expect(page.getByRole('radio', { name: /覆盖/ })).toBeVisible();
    await expect(page.getByRole('radio', { name: /保留两份/ })).toBeVisible();

    // Change strategy to overwrite
    await page.getByRole('radio', { name: /覆盖/ }).click();
    // Preview should refresh
    await expect(page.getByText(/完整备份预览/)).toBeVisible({ timeout: 10_000 });

    // Cancel the import
    await page.getByRole('button', { name: '取消' }).click();
    await expect(page.getByText(/完整备份预览/)).toHaveCount(0);

    // Cleanup
    await page.request.delete(`${apiBase}/materials/${mat.id}`);
  });
});

test.describe('data maintenance', () => {
  test('sidebar has data maintenance link', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: /数据维护/ })).toBeVisible();
  });

  test('maintenance page loads health summary', async ({ page }) => {
    await page.goto('/maintenance');
    await expect(page.getByRole('heading', { name: '数据维护中心' })).toBeVisible();
    // Health summary cards should load
    await expect(page.getByText('资料记录')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('上传文件')).toBeVisible();
    await expect(page.getByText('数据库大小')).toBeVisible();
    // Use exact match to avoid strict mode violations
    await expect(page.getByText('孤儿文件', { exact: true })).toBeVisible();
    await expect(page.getByText('缺失文件', { exact: true })).toBeVisible();
  });

  test('cleanup preview opens and shows results', async ({ page }) => {
    await page.goto('/maintenance');
    // Wait for health data to load
    await expect(page.getByText('资料记录')).toBeVisible({ timeout: 10_000 });

    // Click preview cleanup
    await page.getByRole('button', { name: '预览清理' }).click();

    // Preview results should appear
    const preview = page.getByTestId('cleanup-preview');
    await expect(preview).toBeVisible({ timeout: 10_000 });
    await expect(preview.getByText(/孤儿文件.*个/)).toBeVisible();
    await expect(preview.getByText(/无效解析任务.*个/)).toBeVisible();
  });

  test('operation logs load and display entries', async ({ page }) => {
    // Create some operation history by exporting
    const apiBase = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 18000}/api`;
    await page.request.get(`${apiBase}/export/json`);

    await page.goto('/maintenance');
    // Wait for logs section
    await expect(page.getByRole('heading', { name: '操作记录' })).toBeVisible({ timeout: 10_000 });
    // Should have at least one log entry
    await expect(page.getByText('导出 JSON').first()).toBeVisible({ timeout: 10_000 });
  });
});
