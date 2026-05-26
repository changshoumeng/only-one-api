import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { useSessionStore } from '@/stores/session';
import AppLayout from '@/layouts/AppLayout.vue';
import LoginPage from '@/pages/auth/LoginPage.vue';
import ResetPasswordPage from '@/pages/auth/ResetPasswordPage.vue';
import LlmUsagePage from '@/pages/usage/LlmUsagePage.vue';
import ApiManagePage from '@/pages/api/ApiManagePage.vue';
import KeyManagePage from '@/pages/key/KeyManagePage.vue';
import ChatHistoryPage from '@/pages/chat/ChatHistoryPage.vue';
import NotFoundPage from '@/pages/NotFoundPage.vue';

export const protectedRouteNames = [
  'usage',
  'api-manage',
  'key-manage',
  'chat-history',
] as const;

export const appRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/usage',
  },
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: {
      public: true,
      title: '登录',
    },
  },
  {
    path: '/reset-password',
    name: 'reset-password',
    component: ResetPasswordPage,
    meta: {
      public: true,
      title: '重置密码',
    },
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      {
        path: 'usage',
        name: 'usage',
        component: LlmUsagePage,
        meta: {
          title: '使用量',
          navLabel: '使用量',
        },
      },
      {
        path: 'api-manage',
        name: 'api-manage',
        component: ApiManagePage,
        meta: {
          title: '接口管理',
          navLabel: '接口管理',
        },
      },
      {
        path: 'key-manage',
        name: 'key-manage',
        component: KeyManagePage,
        meta: {
          title: 'key 管理',
          navLabel: 'Key 管理',
        },
      },
      {
        path: 'chat-history',
        name: 'chat-history',
        component: ChatHistoryPage,
        meta: {
          title: '对话历史',
          navLabel: '对话历史',
        },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundPage,
    meta: {
      public: true,
      title: '页面不存在',
    },
  },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: appRoutes,
});

router.beforeEach(async (to) => {
  const session = useSessionStore();
  const isPublic = Boolean(to.meta.public);

  if (isPublic) {
    return true;
  }

  const hasSession = await session.ensureAuthenticated();
  if (!hasSession) {
    return {
      name: 'login',
      query: {
        redirect: to.fullPath,
      },
    };
  }

  return true;
});

router.afterEach((to) => {
  const appName = import.meta.env.VITE_APP_NAME || 'only-one-api';
  document.title = to.meta.title ? `${String(to.meta.title)} - ${appName}` : appName;
});

