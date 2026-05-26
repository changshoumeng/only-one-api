<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { BarChart3, Coins, RefreshCw, Search, Zap } from '@lucide/vue';
import TrendChart from '@/components/base/TrendChart.vue';
import {
  getMoneyChart,
  getRequestChart,
  getTokenChart,
  getUsageSummary,
  type UsageQuery,
} from '@/services/usage';
import type { EChartLinePayload, UsageSummary } from '@/services/types';
import { formatError, formatInteger } from '@/utils/format';

interface ChartView {
  title: string;
  unit: string;
  labels: string[];
  series: Array<{
    name: string;
    values: number[];
  }>;
}

const query = reactive<UsageQuery>({
  before_num: 7,
  unit_type: 'day',
});

const summary = ref<UsageSummary>({
  total_request: '0',
  total_tokens: '0',
  total_price: '0.00',
});
const requestChart = ref<ChartView>(emptyChart('请求次数', '次'));
const tokenChart = ref<ChartView>(emptyChart('Token 消耗', 'tokens'));
const moneyChart = ref<ChartView>(emptyChart('消费金额', '元'));
const isLoading = ref(false);
const errorMessage = ref('');

const metrics = computed(() => [
  {
    label: '接口请求数',
    value: formatInteger(summary.value.total_request),
    hint: '已完成请求总量',
    icon: BarChart3,
  },
  {
    label: 'Token 消耗',
    value: formatInteger(summary.value.total_tokens),
    hint: '输入与输出 Token 汇总',
    icon: Zap,
  },
  {
    label: '已消费金额',
    value: `¥ ${summary.value.total_price}`,
    hint: '按模型单价估算',
    icon: Coins,
  },
]);

function emptyChart(title: string, unit: string): ChartView {
  return {
    title,
    unit,
    labels: [],
    series: [],
  };
}

function toNumber(value: number | string | null | undefined) {
  const result = Number(value ?? 0);
  return Number.isFinite(result) ? result : 0;
}

function chartFromPayload(
  title: string,
  unit: string,
  payload: EChartLinePayload,
  names: string[],
) {
  const labels = payload.xAxis?.data ?? [];
  const series = (payload.series ?? []).map((item, index) => ({
    name: names[index] ?? title,
    values: (item.data ?? []).map(toNumber),
  }));

  return {
    title,
    unit,
    labels,
    series,
  };
}

async function loadUsage() {
  if (Number(query.before_num) <= 0) {
    errorMessage.value = '时间范围必须大于 0';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  try {
    const [nextSummary, requestPayload, tokenPayload, moneyPayload] =
      await Promise.all([
        getUsageSummary(),
        getRequestChart(query),
        getTokenChart(query),
        getMoneyChart(query),
      ]);

    summary.value = nextSummary;
    requestChart.value = chartFromPayload('请求次数', '次', requestPayload, [
      '请求次数',
    ]);
    tokenChart.value = chartFromPayload('Token 消耗', 'tokens', tokenPayload, [
      '输入 Token',
      '输出 Token',
    ]);
    moneyChart.value = chartFromPayload('消费金额', '元', moneyPayload, [
      '消费金额',
    ]);
  } catch (error) {
    errorMessage.value = formatError(error, '使用量数据加载失败');
  } finally {
    isLoading.value = false;
  }
}

onMounted(loadUsage);
</script>

<template>
  <section class="page page-grid2">
    <div class=" page-shell--dashboard page-grid">
      <div class="surface page-panel">
        <form
          class="toolbar-panel toolbar-panel--cluster"
          @submit.prevent="loadUsage"
        >
          <div class="toolbar-copy2">
            <h2 class="section-title">用量查询</h2>
            <p class="subtle">按时间窗口刷新请求、Token 与费用趋势。</p>
          </div>
          <div class="toolbar-controls">
            <label class="compact-field">
              <span>时间范围</span>
              <input
                v-model.number="query.before_num"
                class="field-input compact-input"
                min="1"
                type="number"
              />
            </label>
            <label class="compact-field">
              <span>单位</span>
              <select
                v-model="query.unit_type"
                class="field-input compact-input"
              >
                <option value="day">日</option>
                <option value="month">月</option>
                <option value="year">年</option>
              </select>
            </label>
            <button
              class="button button-primary button-inline"
              type="submit"
              :disabled="isLoading"
            >
              <Search aria-hidden="true" />
              <span>查询</span>
            </button>
            <button
              class="button button-muted button-inline"
              type="button"
              :disabled="isLoading"
              @click="loadUsage"
            >
              <RefreshCw aria-hidden="true" />
              <span>刷新</span>
            </button>
          </div>
        </form>

        <p v-if="errorMessage" class="inline-error" role="alert">
          {{ errorMessage }}
        </p>

        <div class="metric-grid">
          <article
            v-for="metric in metrics"
            :key="metric.label"
            class="metric-card stack-sm"
          >
            <div class="metric-heading">
              <component
                :is="metric.icon"
                class="metric-icon"
                aria-hidden="true"
              />
              <p class="subtle">{{ metric.label }}</p>
            </div>
            <p class="metric-value">{{ metric.value }}</p>
            <p class="subtle">{{ metric.hint }}</p>
          </article>
        </div>

        <div class="chart-grid">
          <TrendChart :chart="requestChart" />
          <TrendChart :chart="tokenChart" />
          <TrendChart :chart="moneyChart" />
        </div>
      </div>
    </div>
  </section>
</template>
