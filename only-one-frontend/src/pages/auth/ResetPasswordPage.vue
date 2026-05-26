<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { KeyRound } from '@lucide/vue';
import { resetPassword } from '@/services/auth';
import { useSessionStore } from '@/stores/session';

const router = useRouter();
const session = useSessionStore();

const form = reactive({
  password: '',
  passwordAgain: '',
});

const errorMessage = ref('');
const isSubmitting = ref(false);

async function handleSubmit() {
  if (isSubmitting.value) {
    return;
  }

  errorMessage.value = '';

  if (!form.password) {
    errorMessage.value = '新密码不能为空';
    return;
  }

  if (form.password.length < 8) {
    errorMessage.value = '新密码长度至少 8 位';
    return;
  }

  if (form.password !== form.passwordAgain) {
    errorMessage.value = '两次输入密码不一致';
    return;
  }

  isSubmitting.value = true;

  try {
    await resetPassword({
      password: form.password,
      password_again: form.passwordAgain,
    });
    session.markAuthenticated();
    await router.push({ name: 'usage' });
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : '修改失败，请重试';
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
         
          <h2 class="auth-visual-title">完成首次登录密码设置</h2>
          <p class="auth-visual-copy">
            设置新密码后即可进入 only-one-api 管理后台。
          </p>
        </div>
      </section>

      <section class="surface auth-card stack" aria-labelledby="reset-title">
        <header class="stack-sm">
         
          <h1 id="reset-title" class="page-title">重置密码</h1>
          <p class="subtle">第一次登录需要设置新密码。</p>
        </header>

        <form class="stack" @submit.prevent="handleSubmit">
          <label class="field-label">
            <span>新密码</span>
            <input
              v-model="form.password"
              class="field-input"
              autocomplete="new-password"
              placeholder="至少 8 位密码"
              type="password"
            />
          </label>
          <label class="field-label">
            <span>确认新密码</span>
            <input
              v-model="form.passwordAgain"
              class="field-input"
              autocomplete="new-password"
              placeholder="再次输入新密码"
              type="password"
            />
          </label>
          <p class="form-error" role="alert">{{ errorMessage }}</p>
          <button
            class="button button-primary"
            type="submit"
            :disabled="isSubmitting"
          >
            <KeyRound aria-hidden="true" />
            <span>{{ isSubmitting ? '修改中' : '修改密码' }}</span>
          </button>
        </form>
      </section>
    </div>
  </main>
</template>
