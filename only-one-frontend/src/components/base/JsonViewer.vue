<script setup lang="ts">
import { computed, ref } from 'vue';
import { Copy } from '@lucide/vue';
import { copyText } from '@/utils/format';

const props = withDefaults(
  defineProps<{
    title: string;
    value: unknown;
    stage?: string;
    emptyText?: string;
    copyId?: string;
  }>(),
  {
    stage: '',
    emptyText: '不可用',
    copyId: '',
  },
);

const copied = ref(false);

const isEmpty = computed(
  () => props.value === null || props.value === undefined || props.value === '',
);

const displayText = computed(() => {
  if (isEmpty.value) {
    return props.emptyText;
  }
  if (typeof props.value === 'string') {
    return props.value;
  }
  try {
    return JSON.stringify(props.value, null, 2);
  } catch {
    return String(props.value);
  }
});

async function copyJson() {
  await copyText(displayText.value);
  copied.value = true;
  window.setTimeout(() => {
    copied.value = false;
  }, 1200);
}
</script>

<template>
  <section class="json-viewer">
    <header class="json-viewer-header">
      <div class="json-viewer-title">
        <h3>{{ title }}</h3>
        <span v-if="stage" class="raw-flag raw-flag-on">{{ stage }}</span>
      </div>
      <button
        class="icon-button icon-button-compact"
        type="button"
        :aria-label="`复制${title}`"
        :disabled="isEmpty"
        @click="copyJson"
      >
        <Copy aria-hidden="true" />
      </button>
    </header>
    <pre class="json-viewer-block" :class="{ 'json-viewer-empty': isEmpty }">{{
      displayText
    }}</pre>
    <p v-if="copied" class="subtle">已复制</p>
  </section>
</template>
