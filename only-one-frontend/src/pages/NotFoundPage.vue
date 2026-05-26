<template>
  <main class="page page-frame">
    <section class="surface auth-card stack">
      <h1 class="page-title">页面不存在</h1>
      <p class="subtle">请返回已知路由继续操作。</p>
      <RouterLink class="button button-secondary" :to="{ name: 'login' }"
        >返回登录</RouterLink
      >
    </section>
  </main>
</template>
