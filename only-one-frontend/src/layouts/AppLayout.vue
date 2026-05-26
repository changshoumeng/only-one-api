<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen } from '@lucide/vue';
import { logout } from '@/services/auth';
import { useSessionStore } from '@/stores/session';
import { primaryNavigation } from '@/router/navigation';

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const sidebarOpen = ref(true);
const isLoggingOut = ref(false);
const logoutError = ref('');

const pageTitle = computed(() => String(route.meta.title || 'only-one-api'));

async function handleLogout() {
  if (isLoggingOut.value) {
    return;
  }

  const confirmed = window.confirm('确定退出登录吗？');
  if (!confirmed) {
    return;
  }

  isLoggingOut.value = true;
  logoutError.value = '';

  try {
    await logout();
    session.clearSession();
    await router.push({ name: 'login' });
  } catch (error) {
    logoutError.value =
      error instanceof Error ? error.message : '退出失败，请稍后重试';
  } finally {
    isLoggingOut.value = false;
  }
}
</script>

<template>
  <div class="app-layout" :class="{ 'app-layout-collapsed': !sidebarOpen }">
    <aside class="app-sidebar" aria-label="主导航">
      <div class="brand-block">
        <div class="brand-mark" aria-hidden="true">1</div>
        <div class="brand-copy">
          <p class="brand-title">LLM API聚合平台</p>
        </div>
      </div>

      <nav class="sidebar-nav">
        <RouterLink
          v-for="item in primaryNavigation"
          :key="item.routeName"
          :to="{ name: item.routeName }"
          class="nav-link"
          active-class="nav-link-active"
        >
          <component :is="item.icon" class="nav-icon" aria-hidden="true" />
          <span class="nav-text">
            <span class="nav-label">{{ item.label }}</span>
            <span class="nav-description">{{ item.description }}</span>
          </span>
        </RouterLink>
      </nav>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <div class="topbar-left">
          <button
            class="icon-button desktop-toggle"
            type="button"
            :aria-label="sidebarOpen ? '收起侧边栏' : '展开侧边栏'"
            @click="sidebarOpen = !sidebarOpen"
          >
            <PanelLeftClose v-if="sidebarOpen" aria-hidden="true" />
            <PanelLeftOpen v-else aria-hidden="true" />
          </button>
          <button
            class="icon-button mobile-toggle"
            type="button"
            aria-label="切换导航"
            @click="sidebarOpen = !sidebarOpen"
          >
            <Menu aria-hidden="true" />
          </button>
          <h1 class="topbar-title">{{ pageTitle }}</h1>
        </div>

        <div class="topbar-actions">
          <div class="user-pill" aria-label="当前用户">
            <span class="user-avatar" aria-hidden="true">{{
              session.displayName.slice(0, 1)
            }}</span>
            <span>{{ session.displayName }}</span>
          </div>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="isLoggingOut"
            @click="handleLogout"
          >
            <LogOut aria-hidden="true" />
            <span>{{ isLoggingOut ? '退出中' : '退出登录' }}</span>
          </button>
        </div>
      </header>

      <p v-if="logoutError" class="global-error" role="alert">
        {{ logoutError }}
      </p>

      <main class="content-frame">
        <RouterView />
      </main>
    </div>
  </div>
</template>
