<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { LogIn } from '@lucide/vue';
import { login } from '@/services/auth';
import { useSessionStore } from '@/stores/session';

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const form = reactive({
  username: '',
  password: '',
});

const errorMessage = ref('');
const isSubmitting = ref(false);

async function handleSubmit() {
  if (isSubmitting.value) {
    return;
  }

  errorMessage.value = '';

  if (!form.username.trim()) {
    errorMessage.value = '用户名不能为空';
    return;
  }

  if (!form.password) {
    errorMessage.value = '密码不能为空';
    return;
  }

  isSubmitting.value = true;

  try {
    const response = await login({
      username: form.username.trim(),
      password: form.password,
    });

    session.markAuthenticated(form.username.trim());

    if (response.data?.is_first_login === 1) {
      await router.push({ name: 'reset-password' });
      return;
    }

    const redirect =
      typeof route.query.redirect === 'string'
        ? route.query.redirect
        : '/usage';
    await router.push(redirect);
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : '登录失败，请重试';
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <main class="page page-frame">
    <div class="auth-page">
      <section class="auth-visual" aria-hidden="true">
        <div class="auth-visual-panel">
       
          <h2 class="auth-visual-title">统一管理个人 LLM 接口</h2>
          <p class="auth-visual-copy">
            聚合模型供应商、访问密钥、用量统计和对话历史，保持轻量、直接、可控。
          </p>
        </div>
      </section>

      <section class="surface auth-card stack" aria-labelledby="login-title">
        <header class="stack-sm">
        
          <h1 id="login-title" class="page-title">登录</h1>
          <p class="subtle">账号第一次登录后需要重新设置新密码。</p>
        </header>

        <form class="stack" @submit.prevent="handleSubmit">
          <label class="field-label">
            <span>用户名</span>
            <input
              v-model="form.username"
              class="field-input"
              autocomplete="username"
              placeholder="例如：tony"
              type="text"
            />
          </label>
          <label class="field-label">
            <span>密码</span>
            <input
              v-model="form.password"
              class="field-input"
              autocomplete="current-password"
              placeholder="至少 8 位密码"
              type="password"
            />
          </label>
          <p class="form-error" role="alert">{{ errorMessage }}</p>
          <button
            class="button button-primary"
            type="submit"
            :disabled="isSubmitting"
          >
            <LogIn aria-hidden="true" />
            <span>{{ isSubmitting ? '登录中' : '登录' }}</span>
          </button>
        </form>
      </section>
    </div>
  </main>
</template>
