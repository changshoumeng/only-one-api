<script setup lang="ts">
import { computed } from 'vue';

interface TrendChartSeries {
  name: string;
  values: number[];
}

interface TrendChartModel {
  title: string;
  unit: string;
  labels: string[];
  series: TrendChartSeries[];
}

const props = defineProps<{
  chart: TrendChartModel;
}>();

const maxValue = computed(() => {
  const values = props.chart.series.flatMap((item) => item.values);
  return Math.max(...values, 0);
});

function barHeight(value: number) {
  if (maxValue.value <= 0) {
    return '2px';
  }

  return `${Math.max(4, Math.round((value / maxValue.value) * 120))}px`;
}
</script>

<template>
  <article class="surface chart-card stack-sm">
    <header class="chart-header">
      <div>
        <h3 class="section-title">{{ chart.title }}</h3>
        <p class="subtle">单位：{{ chart.unit }}</p>
      </div>
    </header>

    <div v-if="chart.labels.length && chart.series.length" class="mini-chart" aria-label="趋势图">
      <div v-for="(label, index) in chart.labels" :key="label + index" class="chart-column">
        <div class="chart-bars">
          <span
            v-for="series in chart.series"
            :key="series.name"
            class="chart-bar"
            :style="{ height: barHeight(series.values[index] || 0) }"
            :title="`${series.name}: ${series.values[index] || 0}`"
          />
        </div>
        <span class="chart-label">{{ label }}</span>
      </div>
    </div>

    <p v-else class="empty-copy">暂无趋势数据</p>

    <div v-if="chart.series.length > 1" class="chart-legend">
      <span v-for="series in chart.series" :key="series.name">{{ series.name }}</span>
    </div>
  </article>
</template>
