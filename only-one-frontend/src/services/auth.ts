import { requestEnvelope } from './http';

export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResult {
  is_first_login?: number;
}

export interface ResetPasswordPayload {
  password: string;
  password_again: string;
}

export async function login(payload: LoginPayload) {
  return requestEnvelope<LoginResult>({
    method: 'POST',
    url: '/backend/login',
    data: payload,
  });
}

export async function resetPassword(payload: ResetPasswordPayload) {
  return requestEnvelope({
    method: 'POST',
    url: '/backend/reset-password',
    data: payload,
  });
}

export async function logout() {
  return requestEnvelope({
    method: 'GET',
    url: '/backend/logout',
  });
}

export async function probeAuthenticatedSession() {
  return requestEnvelope({
    method: 'GET',
    url: '/backend/api-manage/provider/select',
  });
}

