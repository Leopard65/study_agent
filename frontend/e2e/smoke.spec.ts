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

    await page.getByPlaceholder('关键词检索资料内容...').fill(marker);
    await page.getByRole('button', { name: '搜索' }).click();
    await expect(page.getByRole('heading', { name: /搜索结果/ })).toBeVisible();
    await expect(page.getByText(filename).first()).toBeVisible();

    const materialRow = page
      .getByText(filename)
      .last()
      .locator('xpath=ancestor::div[.//button[normalize-space()="查看"]][1]');
    await materialRow.getByRole('button', { name: '查看' }).click();
    await expect(page.locator('pre').filter({ hasText: `关键词 ${marker}` })).toBeVisible();
    await page.getByRole('button', { name: '×' }).click();

    page.on('dialog', dialog => dialog.accept());
    await materialRow.getByRole('button', { name: '删除' }).click();
    await expect(page.getByText(filename)).toHaveCount(0);
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
});
