export function formatError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function formatInteger(value: string | number | null | undefined) {
  const numberValue = Number(value ?? 0);
  return Number.isFinite(numberValue) ? numberValue.toLocaleString('zh-CN') : String(value ?? '0');
}

export function formatCurrency(value: string | number | null | undefined, maxFractionDigits = 4) {
  const numberValue = Number(value ?? 0);
  if (!Number.isFinite(numberValue)) {
    return String(value ?? '--');
  }

  return numberValue.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxFractionDigits,
  });
}

export function shortSecret(value: string) {
  if (value.length <= 14) {
    return value;
  }

  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

export async function copyText(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.style.position = 'fixed';
  textArea.style.opacity = '0';
  document.body.appendChild(textArea);
  textArea.select();
  document.execCommand('copy');
  document.body.removeChild(textArea);
}
