<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import {
  CheckCircle2,
  Clipboard,
  Database,
  Edit3,
  PlayCircle,
  Plus,
  RefreshCw,
  Terminal,
  Trash2,
  XCircle,
} from '@lucide/vue';
import {
  createModel,
  createProvider,
  deleteModel,
  deleteProvider,
  listModels,
  listProviderOptions,
  listProviders,
  testModel,
  toggleModelStatus,
  updateModel,
  updateProvider,
  type ModelPayload,
  type ProviderPayload,
} from '@/services/apiManage';
import type {
  BillingUnit,
  ModelItem,
  ModelTestResult,
  ProviderItem,
  SelectOption,
} from '@/services/types';
import { copyText, formatError } from '@/utils/format';

type ProviderDialogMode = 'create' | 'edit';
type ModelDialogMode = 'create' | 'edit';

const providerPage = reactive({ page: 1, perPage: 10 });
const modelPage = reactive({ page: 1, perPage: 10 });
const providers = ref<ProviderItem[]>([]);
const models = ref<ModelItem[]>([]);
const providerTotal = ref(0);
const modelTotal = ref(0);
const providerOptions = ref<SelectOption[]>([]);
const isLoading = ref(false);
const isSaving = ref(false);
const errorMessage = ref('');

const providerDialogOpen = ref(false);
const providerDialogMode = ref<ProviderDialogMode>('create');
const providerForm = reactive<ProviderPayload>({
  provider_name: '',
  provider_english_name: '',
  api_key: '',
  base_url: '',
});

const modelDialogOpen = ref(false);
const modelDialogMode = ref<ModelDialogMode>('create');
const modelForm = reactive<ModelPayload>({
  provider_english_name: '',
  model_name: '',
  model_id: '',
  billing_unit: 'per_thousand_tokens',
  input_unit_price: '',
  output_unit_price: '',
  default_params: '',
  status: true,
});

const testDialogOpen = ref(false);
const testingModel = ref<ModelItem | null>(null);
const modelTestResult = ref<ModelTestResult | null>(null);
const isTestingModel = ref(false);
const testErrorMessage = ref('');
const copySuccess = ref(false);

const providerPageCount = computed(() =>
  Math.max(1, Math.ceil(providerTotal.value / providerPage.perPage)),
);
const modelPageCount = computed(() =>
  Math.max(1, Math.ceil(modelTotal.value / modelPage.perPage)),
);
const modelTestDisplayCurl = computed(() => {
  const request = modelTestResult.value?.request;
  return request?.curl_display || request?.curl || '';
});
const modelTestResponseRaw = computed(() =>
  formatJsonForDisplay(modelTestResult.value?.response?.raw),
);
const modelTestStatusMeta = computed(() => {
  if (isTestingModel.value) {
    return {
      tone: 'running',
      title: '正在测试模型接口',
      description: '已发出测试请求，等待模型返回。',
    };
  }

  const status = modelTestResult.value?.test_status;
  if (status === 'success') {
    return {
      tone: 'success',
      title: '接口可用',
      description: '已收到 OpenAI 兼容的文本回复。',
    };
  }

  const titles: Record<string, string> = {
    auth_failed: '网关密钥不可用',
    model_disabled: '模型已停用',
    model_not_found: '模型不存在',
    upstream_failed: '上游调用失败',
    invalid_response: '返回格式异常',
    timeout: '测试超时',
  };

  return {
    tone: status ? 'error' : 'idle',
    title: status ? titles[status] ?? '接口不可用' : '等待测试',
    description:
      modelTestResult.value?.error?.message ||
      testErrorMessage.value ||
      '打开弹窗后会自动发起测试。',
  };
});

function resetProviderForm() {
  providerForm.id = undefined;
  providerForm.provider_name = '';
  providerForm.provider_english_name = '';
  providerForm.api_key = '';
  providerForm.base_url = '';
}

function resetModelForm() {
  modelForm.id = undefined;
  modelForm.status = true;
  modelForm.provider_english_name = providerOptions.value[0]?.value ?? '';
  modelForm.model_name = '';
  modelForm.model_id = '';
  modelForm.billing_unit = 'per_thousand_tokens';
  modelForm.input_unit_price = '';
  modelForm.output_unit_price = '';
  modelForm.default_params = '';
}

async function loadAll() {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    const [providerResult, modelResult, options] = await Promise.all([
      listProviders(providerPage),
      listModels(modelPage),
      listProviderOptions(),
    ]);
    providers.value = providerResult.rows;
    providerTotal.value = providerResult.count;
    models.value = modelResult.rows;
    modelTotal.value = modelResult.count;
    providerOptions.value = options;
    if (!modelForm.provider_english_name) {
      modelForm.provider_english_name = options[0]?.value ?? '';
    }
  } catch (error) {
    errorMessage.value = formatError(error, '接口管理数据加载失败');
  } finally {
    isLoading.value = false;
  }
}

function openCreateProvider() {
  resetProviderForm();
  providerDialogMode.value = 'create';
  providerDialogOpen.value = true;
}

function openEditProvider(item: ProviderItem) {
  providerForm.id = item.id;
  providerForm.provider_name = item.provider_name;
  providerForm.provider_english_name = item.provider_english_name;
  providerForm.api_key = item.api_key ?? '';
  providerForm.base_url = item.base_url;
  providerDialogMode.value = 'edit';
  providerDialogOpen.value = true;
}

async function submitProvider() {
  if (
    !providerForm.provider_name ||
    !providerForm.provider_english_name ||
    !providerForm.api_key ||
    !providerForm.base_url
  ) {
    errorMessage.value = '请完整填写提供商表单';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    if (providerDialogMode.value === 'create') {
      await createProvider(providerForm);
    } else {
      await updateProvider(providerForm);
    }
    providerDialogOpen.value = false;
    await loadAll();
  } catch (error) {
    errorMessage.value = formatError(error, '保存提供商失败');
  } finally {
    isSaving.value = false;
  }
}

async function removeProvider(item: ProviderItem) {
  if (
    !window.confirm(
      `确认删除提供商「${item.provider_name}」吗？相关模型也会被删除。`,
    )
  ) {
    return;
  }

  await runAction(() => deleteProvider(item.id), '删除提供商失败');
}

function openCreateModel() {
  resetModelForm();
  modelDialogMode.value = 'create';
  modelDialogOpen.value = true;
}

function openEditModel(item: ModelItem) {
  modelForm.id = item.id;
  modelForm.status = item.status;
  modelForm.provider_english_name = item.provider_english_name;
  modelForm.model_name = item.model_name;
  modelForm.model_id = item.model_id;
  modelForm.billing_unit = item.billing_unit;
  modelForm.input_unit_price = String(item.input_unit_price);
  modelForm.output_unit_price = String(item.output_unit_price);
  modelForm.default_params = item.default_params ?? '';
  modelDialogMode.value = 'edit';
  modelDialogOpen.value = true;
}

async function submitModel() {
  if (
    !modelForm.provider_english_name ||
    !modelForm.model_name ||
    !modelForm.model_id
  ) {
    errorMessage.value = '请完整填写模型表单';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    const payload = {
      ...modelForm,
      billing_unit: modelForm.billing_unit as BillingUnit,
      default_params: modelForm.default_params || null,
    };
    if (modelDialogMode.value === 'create') {
      await createModel(payload);
    } else {
      await updateModel(payload);
    }
    modelDialogOpen.value = false;
    await loadAll();
  } catch (error) {
    errorMessage.value = formatError(error, '保存模型失败');
  } finally {
    isSaving.value = false;
  }
}

async function switchModelStatus(item: ModelItem) {
  if (
    !window.confirm(
      `确认${item.status ? '停用' : '启用'}模型「${item.model_name}」吗？`,
    )
  ) {
    return;
  }

  await runAction(() => toggleModelStatus(item.id), '修改模型状态失败');
}

async function removeModel(item: ModelItem) {
  if (!window.confirm(`确认删除模型「${item.model_name}」吗？`)) {
    return;
  }

  await runAction(() => deleteModel(item.id), '删除模型失败');
}

function formatJsonForDisplay(value: unknown) {
  if (value === undefined || value === null || value === '') {
    return '';
  }

  if (typeof value === 'string') {
    return value;
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function openTestModel(item: ModelItem) {
  testingModel.value = item;
  modelTestResult.value = null;
  testErrorMessage.value = '';
  copySuccess.value = false;
  testDialogOpen.value = true;
  void runModelTest();
}

async function runModelTest() {
  if (!testingModel.value) {
    return;
  }

  isTestingModel.value = true;
  testErrorMessage.value = '';
  copySuccess.value = false;
  modelTestResult.value = null;

  try {
    modelTestResult.value = await testModel(testingModel.value.id);
  } catch (error) {
    modelTestResult.value = null;
    testErrorMessage.value = formatError(error, '模型测试失败');
  } finally {
    isTestingModel.value = false;
  }
}

async function copyModelTestCurl() {
  const command = modelTestResult.value?.request.curl;
  if (!command) {
    testErrorMessage.value = '暂无可复制的测试命令';
    return;
  }

  try {
    await copyText(command);
    copySuccess.value = true;
    window.setTimeout(() => {
      copySuccess.value = false;
    }, 1800);
  } catch (error) {
    copySuccess.value = false;
    testErrorMessage.value = formatError(error, '复制失败，请手动选择命令复制');
  }
}

function closeModelTestDialog() {
  testDialogOpen.value = false;
  testingModel.value = null;
  modelTestResult.value = null;
  testErrorMessage.value = '';
  copySuccess.value = false;
}

async function runAction(action: () => Promise<unknown>, fallback: string) {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    await action();
    await loadAll();
  } catch (error) {
    errorMessage.value = formatError(error, fallback);
  } finally {
    isLoading.value = false;
  }
}

async function changeProviderPage(nextPage: number) {
  providerPage.page = Math.min(Math.max(1, nextPage), providerPageCount.value);
  await loadAll();
}

async function changeModelPage(nextPage: number) {
  modelPage.page = Math.min(Math.max(1, nextPage), modelPageCount.value);
  await loadAll();
}

onMounted(loadAll)
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
            <h2 class="section-title">模型提供商</h2>
            <p class="subtle">
              配置 OpenAI 兼容接口的供应商名称、英文标识、API Key 和 base-url。
            </p>
          </div>
          <div class="toolbar-actions">
            <button
              class="button button-muted button-inline"
              type="button"
              :disabled="isLoading"
              @click="loadAll"
            >
              <RefreshCw aria-hidden="true" />
              <span>刷新</span>
            </button>
            <button
              class="button button-primary button-inline"
              type="button"
              @click="openCreateProvider"
            >
              <Plus aria-hidden="true" />
              <span>新增提供商</span>
            </button>
          </div>
        </header>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>提供商名称</th>
                <th>英文名称</th>
                <th>base-url</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="provider in providers" :key="provider.id">
                <td>{{ provider.row_id }}</td>
                <td>{{ provider.provider_name }}</td>
                <td>
                  <code>{{ provider.provider_english_name }}</code>
                </td>
                <td class="text-clip">{{ provider.base_url }}</td>
                <td>{{ provider.create_time }}</td>
                <td>
                  <div class="row-actions">
                    <button
                      class="button button-muted button-inline"
                      type="button"
                      @click="openEditProvider(provider)"
                    >
                      <Edit3 aria-hidden="true" />
                      <span>修改</span>
                    </button>
                    <button
                      class="button button-danger button-inline"
                      type="button"
                      @click="removeProvider(provider)"
                    >
                      <Trash2 aria-hidden="true" />
                      <span>删除</span>
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="!providers.length">
                <td class="empty-table" colspan="6">暂无提供商</td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="pagination-bar">
          <span>共 {{ providerTotal }} 条</span>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="providerPage.page <= 1"
            @click="changeProviderPage(providerPage.page - 1)"
          >
            上一页
          </button>
          <span>{{ providerPage.page }} / {{ providerPageCount }}</span>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="providerPage.page >= providerPageCount"
            @click="changeProviderPage(providerPage.page + 1)"
          >
            下一页
          </button>
        </footer>
      </section>

      <section class="surface data-section">
        <header class="section-toolbar">
          <div>
            <h2 class="section-title">模型接口</h2>
            <p class="subtle">
              维护模型名称、模型 ID、计费单位、输入输出单价和默认参数。
            </p>
          </div>
          <button
            class="button button-primary button-inline"
            type="button"
            @click="openCreateModel"
          >
            <Database aria-hidden="true" />
            <span>新增模型接口</span>
          </button>
        </header>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>状态</th>
                <th>ID</th>
                <th>提供商</th>
                <th>模型名称</th>
                <th>模型 ID</th>
                <th>输入单价/千 token</th>
                <th>输出单价/千 token</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="model in models" :key="model.id">
                <td>
                  <button
                    class="status-pill"
                    :class="model.status ? 'status-on' : 'status-off'"
                    type="button"
                    @click="switchModelStatus(model)"
                  >
                    {{ model.status ? '可用' : '停用' }}
                  </button>
                </td>
                <td>{{ model.row_id }}</td>
                <td>
                  <code>{{ model.provider_english_name }}</code>
                </td>
                <td>{{ model.model_name }}</td>
                <td>
                  <code>{{ model.model_id }}</code>
                </td>
                <td>{{ model.input_unit_price_thousand }}</td>
                <td>{{ model.output_unit_price_thousand }}</td>
                <td>{{ model.create_time }}</td>
                <td>
                  <div class="row-actions">
                    <button
                      class="button button-secondary button-inline"
                      type="button"
                      @click="openTestModel(model)"
                    >
                      <PlayCircle aria-hidden="true" />
                      <span>测试</span>
                    </button>
                    <button
                      class="button button-muted button-inline"
                      type="button"
                      @click="openEditModel(model)"
                    >
                      <Edit3 aria-hidden="true" />
                      <span>修改</span>
                    </button>
                    <button
                      class="button button-danger button-inline"
                      type="button"
                      @click="removeModel(model)"
                    >
                      <Trash2 aria-hidden="true" />
                      <span>删除</span>
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="!models.length">
                <td class="empty-table" colspan="9">暂无模型接口</td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="pagination-bar">
          <span>共 {{ modelTotal }} 条</span>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="modelPage.page <= 1"
            @click="changeModelPage(modelPage.page - 1)"
          >
            上一页
          </button>
          <span>{{ modelPage.page }} / {{ modelPageCount }}</span>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="modelPage.page >= modelPageCount"
            @click="changeModelPage(modelPage.page + 1)"
          >
            下一页
          </button>
        </footer>
      </section>
    </div>

    <div v-if="providerDialogOpen" class="modal-backdrop" role="presentation">
      <section
        class="surface modal-panel stack"
        role="dialog"
        aria-modal="true"
        aria-labelledby="provider-dialog-title"
      >
        <header class="section-toolbar">
          <h2 id="provider-dialog-title" class="section-title">
            {{
              providerDialogMode === 'create'
                ? '新增模型提供商'
                : '修改模型提供商'
            }}
          </h2>
          <button
            class="icon-button"
            type="button"
            aria-label="关闭"
            @click="providerDialogOpen = false"
          >
            ×
          </button>
        </header>
        <form class="form-grid" @submit.prevent="submitProvider">
          <label class="field-label">
            <span>提供商名称</span>
            <input
              v-model="providerForm.provider_name"
              class="field-input"
              required
            />
          </label>
          <label class="field-label">
            <span>提供商英文名称</span>
            <input
              v-model="providerForm.provider_english_name"
              class="field-input"
              required
            />
          </label>
          <label class="field-label">
            <span>api-key</span>
            <input
              v-model="providerForm.api_key"
              class="field-input"
              required
            />
          </label>
          <label class="field-label">
            <span>base-url</span>
            <input
              v-model="providerForm.base_url"
              class="field-input"
              placeholder="https://example.com/v1"
              required
            />
          </label>
          <footer class="modal-actions">
            <button
              class="button button-muted"
              type="button"
              @click="providerDialogOpen = false"
            >
              取消
            </button>
            <button
              class="button button-primary"
              type="submit"
              :disabled="isSaving"
            >
              保存
            </button>
          </footer>
        </form>
      </section>
    </div>

    <div v-if="modelDialogOpen" class="modal-backdrop" role="presentation">
      <section
        class="surface modal-panel stack"
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-dialog-title"
      >
        <header class="section-toolbar">
          <h2 id="model-dialog-title" class="section-title">
            {{ modelDialogMode === 'create' ? '新增模型接口' : '修改模型接口' }}
          </h2>
          <button
            class="icon-button"
            type="button"
            aria-label="关闭"
            @click="modelDialogOpen = false"
          >
            ×
          </button>
        </header>
        <form class="form-grid" @submit.prevent="submitModel">
          <label class="field-label">
            <span>提供商英文名称</span>
            <select
              v-model="modelForm.provider_english_name"
              class="field-input"
              required
            >
              <option
                v-for="option in providerOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </label>
          <label class="field-label">
            <span>模型名称</span>
            <input
              v-model="modelForm.model_name"
              class="field-input"
              required
            />
          </label>
          <label class="field-label">
            <span>模型 ID</span>
            <input v-model="modelForm.model_id" class="field-input" required />
          </label>
          <label class="field-label">
            <span>计费单位</span>
            <select
              v-model="modelForm.billing_unit"
              class="field-input"
              required
            >
              <option value="per_thousand_tokens">千 Token</option>
              <option value="per_million_tokens">百万 Token</option>
              <option value="per_image">单张图片</option>
            </select>
          </label>
          <label class="field-label">
            <span>模型输入单价</span>
            <input
              v-model="modelForm.input_unit_price"
              class="field-input"
              min="0"
              step="0.0000001"
              type="number"
              required
            />
          </label>
          <label class="field-label">
            <span>模型输出单价</span>
            <input
              v-model="modelForm.output_unit_price"
              class="field-input"
              min="0"
              step="0.0000001"
              type="number"
              required
            />
          </label>
          <label class="field-label form-span-2">
            <span>模型默认参数</span>
            <textarea
              v-model="modelForm.default_params"
              class="field-input text-area"
              placeholder='{&#10;  "thinking": { "type": "enabled" }&#10;}'
            />
          </label>
          <label
            v-if="modelDialogMode === 'edit'"
            class="checkbox-row form-span-2"
          >
            <input v-model="modelForm.status" type="checkbox" />
            <span>模型可用</span>
          </label>
          <footer class="modal-actions form-span-2">
            <button
              class="button button-muted"
              type="button"
              @click="modelDialogOpen = false"
            >
              取消
            </button>
            <button
              class="button button-primary"
              type="submit"
              :disabled="isSaving"
            >
              保存
            </button>
          </footer>
        </form>
      </section>
    </div>

    <div v-if="testDialogOpen" class="modal-backdrop" role="presentation">
      <section
        class="surface modal-panel modal-panel-wide stack"
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-test-dialog-title"
      >
        <header class="section-toolbar">
          <div>
            <h2 id="model-test-dialog-title" class="section-title">
              测试模型接口：{{ testingModel?.model_name }}
            </h2>
            <p class="subtle">
              {{ testingModel?.provider_english_name }} /
              {{ testingModel?.model_id }}
            </p>
          </div>
          <button
            class="icon-button"
            type="button"
            aria-label="关闭"
            @click="closeModelTestDialog"
          >
            ×
          </button>
        </header>

        <section
          class="test-status-panel"
          :class="`test-status-${modelTestStatusMeta.tone}`"
          aria-live="polite"
        >
          <RefreshCw
            v-if="isTestingModel"
            class="test-status-icon spin-icon"
            aria-hidden="true"
          />
          <CheckCircle2
            v-else-if="modelTestResult?.test_status === 'success'"
            class="test-status-icon"
            aria-hidden="true"
          />
          <XCircle
            v-else
            class="test-status-icon"
            aria-hidden="true"
          />
          <div class="stack-sm">
            <h3 class="test-status-title">{{ modelTestStatusMeta.title }}</h3>
            <p class="subtle">{{ modelTestStatusMeta.description }}</p>
            <div v-if="modelTestResult?.response" class="test-meta-row">
              <span v-if="modelTestResult.response.duration_ms !== undefined">
                耗时 {{ modelTestResult.response.duration_ms }}ms
              </span>
              <span v-if="modelTestResult.response.http_status">
                HTTP {{ modelTestResult.response.http_status }}
              </span>
              <span v-if="modelTestResult.response.request_id">
                request_id {{ modelTestResult.response.request_id }}
              </span>
              <span v-if="modelTestResult.tested_at">
                {{ modelTestResult.tested_at }}
              </span>
            </div>
          </div>
        </section>

        <section class="test-block">
          <header class="test-block-header">
            <div class="test-block-heading">
              <Terminal aria-hidden="true" />
              <h3>复制到终端测试</h3>
            </div>
            <div class="toolbar-actions">
              <span v-if="copySuccess" class="copy-note">已复制</span>
              <button
                class="button button-muted button-inline"
                type="button"
                :disabled="!modelTestResult?.request.curl"
                @click="copyModelTestCurl"
              >
                <Clipboard aria-hidden="true" />
                <span>复制</span>
              </button>
            </div>
          </header>
          <pre class="code-scroll"><code>{{ modelTestDisplayCurl || '正在生成测试命令...' }}</code></pre>
        </section>

        <section class="test-block">
          <header class="test-block-header">
            <div class="test-block-heading">
              <Database aria-hidden="true" />
              <h3>自动测试结果</h3>
            </div>
          </header>

          <div v-if="isTestingModel" class="test-placeholder">
            正在等待模型接口返回...
          </div>
          <div v-else-if="testErrorMessage" class="inline-error" role="alert">
            {{ testErrorMessage }}
          </div>
          <div v-else-if="modelTestResult" class="stack">
            <div
              v-if="modelTestResult.response?.content"
              class="test-content-panel"
            >
              {{ modelTestResult.response.content }}
            </div>
            <div v-if="modelTestResult.error" class="inline-error">
              {{ modelTestResult.error.message }}
            </div>
            <pre
              v-if="modelTestResponseRaw"
              class="code-scroll code-scroll-tall"
            ><code>{{ modelTestResponseRaw }}</code></pre>
          </div>
          <div v-else class="test-placeholder">
            暂无测试结果
          </div>
        </section>

        <footer class="modal-actions">
          <button
            class="button button-muted"
            type="button"
            :disabled="isTestingModel"
            @click="runModelTest"
          >
            <RefreshCw aria-hidden="true" />
            <span>重试</span>
          </button>
          <button
            class="button button-primary"
            type="button"
            @click="closeModelTestDialog"
          >
            关闭
          </button>
        </footer>
      </section>
    </div>
  </section>
</template>
