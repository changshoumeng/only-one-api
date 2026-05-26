<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { Copy, Plus, RefreshCw, Save, Trash2 } from '@lucide/vue';
import {
  createKey,
  deleteKey,
  listKeys,
  toggleKeyStatus,
  updateKeyRemark,
} from '@/services/apiManage';
import type { KeyItem } from '@/services/types';
import { copyText, formatError, shortSecret } from '@/utils/format';

const page = reactive({ page: 1, perPage: 10 });
const keys = ref<KeyItem[]>([]);
const total = ref(0);
const isLoading = ref(false);
const errorMessage = ref('');
const copiedKeyId = ref('');
const savingRemarkId = ref('');
const remarks = reactive<Record<string, string>>({});

const pageCount = computed(() =>
  Math.max(1, Math.ceil(total.value / page.perPage)),
);

async function loadKeys() {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    const result = await listKeys(page);
    keys.value = result.rows;
    total.value = result.count;
    for (const item of result.rows) {
      remarks[item.id] = item.remark ?? '';
    }
  } catch (error) {
    errorMessage.value = formatError(error, '密钥列表加载失败');
  } finally {
    isLoading.value = false;
  }
}

async function addKey() {
  await runAction(() => createKey(), '新增 key 失败');
}

async function switchKeyStatus(item: KeyItem) {
  if (!window.confirm(`确认${item.status ? '停用' : '启用'}这个 key 吗？`)) {
    return;
  }

  await runAction(() => toggleKeyStatus(item.id), '修改 key 状态失败');
}

async function removeKey(item: KeyItem) {
  if (!window.confirm('确认删除这个 key 吗？')) {
    return;
  }

  await runAction(() => deleteKey(item.id), '删除 key 失败');
}

async function saveRemark(item: KeyItem) {
  savingRemarkId.value = item.id;
  errorMessage.value = '';

  try {
    await updateKeyRemark(item.id, remarks[item.id] ?? '');
    await loadKeys();
  } catch (error) {
    errorMessage.value = formatError(error, '保存备注失败');
  } finally {
    savingRemarkId.value = '';
  }
}

async function copyKey(item: KeyItem) {
  try {
    await copyText(item.api_key);
    copiedKeyId.value = item.id;
    window.setTimeout(() => {
      if (copiedKeyId.value === item.id) {
        copiedKeyId.value = '';
      }
    }, 1600);
  } catch (error) {
    errorMessage.value = formatError(error, '复制失败');
  }
}

async function runAction(action: () => Promise<unknown>, fallback: string) {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    await action();
    await loadKeys();
  } catch (error) {
    errorMessage.value = formatError(error, fallback);
  } finally {
    isLoading.value = false;
  }
}

async function changePage(nextPage: number) {
  page.page = Math.min(Math.max(1, nextPage), pageCount.value);
  await loadKeys();
}

onMounted(loadKeys);
</script>

<template>
  <section class="page page-grid">
    <div class=" page-shell--data page-grid">
      <p v-if="errorMessage" class="inline-error" role="alert">
        {{ errorMessage }}
      </p>

      <section class="surface data-section">
        <header class="section-toolbar">
          <div>
            <h2 class="section-title">密钥列表</h2>
            <p class="subtle">
              新增密钥后请及时复制保存，列表中支持备注的即时保存。
            </p>
          </div>
          <div class="toolbar-actions">
            <button
              class="button button-muted button-inline"
              type="button"
              :disabled="isLoading"
              @click="loadKeys"
            >
              <RefreshCw aria-hidden="true" />
              <span>刷新</span>
            </button>
            <button
              class="button button-primary button-inline"
              type="button"
              :disabled="isLoading"
              @click="addKey"
            >
              <Plus aria-hidden="true" />
              <span>新增 LLM key</span>
            </button>
          </div>
        </header>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>状态</th>
                <th>ID</th>
                <th>LLM key</th>
                <th>备注</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in keys" :key="item.id">
                <td>
                  <button
                    class="status-pill"
                    :class="item.status ? 'status-on' : 'status-off'"
                    type="button"
                    @click="switchKeyStatus(item)"
                  >
                    {{ item.status ? '可用' : '停用' }}
                  </button>
                </td>
                <td>{{ item.row_id }}</td>
                <td>
                  <div class="secret-cell">
                    <code>{{ shortSecret(item.api_key) }}</code>
                    <button
                      class="icon-button"
                      type="button"
                      :aria-label="`复制 key ${item.row_id}`"
                      @click="copyKey(item)"
                    >
                      <Copy aria-hidden="true" />
                    </button>
                    <span v-if="copiedKeyId === item.id" class="copy-note"
                      >已复制</span
                    >
                  </div>
                </td>
                <td>
                  <div class="remark-editor">
                    <input
                      v-model="remarks[item.id]"
                      class="field-input compact-input"
                      placeholder="填写备注"
                    />
                    <button
                      class="button button-muted button-inline button-action"
                      type="button"
                      :disabled="savingRemarkId === item.id"
                      @click="saveRemark(item)"
                    >
                      <Save aria-hidden="true" />
                      <span>保存</span>
                    </button>
                  </div>
                </td>
                <td>{{ item.create_time }}</td>
                <td>
                  <button
                    class="button button-danger button-inline"
                    type="button"
                    @click="removeKey(item)"
                  >
                    <Trash2 aria-hidden="true" />
                    <span>删除</span>
                  </button>
                </td>
              </tr>
              <tr v-if="!keys.length">
                <td class="empty-table" colspan="6">暂无 key</td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="pagination-bar">
          <span>共 {{ total }} 条</span>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="page.page <= 1"
            @click="changePage(page.page - 1)"
          >
            上一页
          </button>
          <span>{{ page.page }} / {{ pageCount }}</span>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="page.page >= pageCount"
            @click="changePage(page.page + 1)"
          >
            下一页
          </button>
        </footer>
      </section>
    </div>
  </section>
</template>
