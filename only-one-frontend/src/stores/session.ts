import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { probeAuthenticatedSession } from '@/services/auth';

type AuthProbeState = 'idle' | 'checking' | 'checked';

export const useSessionStore = defineStore('session', () => {
  const isAuthenticated = ref(false);
  const username = ref('');
  const probeState = ref<AuthProbeState>('idle');

  const displayName = computed(() => username.value || '管理员');

  function markAuthenticated(nextUsername?: string) {
    isAuthenticated.value = true;
    username.value = nextUsername || username.value || '管理员';
    probeState.value = 'checked';
  }

  function clearSession() {
    isAuthenticated.value = false;
    username.value = '';
    probeState.value = 'checked';
  }

  async function ensureAuthenticated() {
    if (isAuthenticated.value) {
      return true;
    }

    if (probeState.value === 'checking') {
      return isAuthenticated.value;
    }

    probeState.value = 'checking';

    try {
      await probeAuthenticatedSession();
      markAuthenticated();
      return true;
    } catch {
      clearSession();
      return false;
    }
  }

  return {
    isAuthenticated,
    username,
    displayName,
    probeState,
    markAuthenticated,
    clearSession,
    ensureAuthenticated,
  };
});

