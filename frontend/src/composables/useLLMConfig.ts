import { ref, watch } from "vue";

const STORAGE_KEY = "llm_config";

interface LLMConfig {
  base_url: string;
  api_key: string;
  model: string;
}

const defaultConfig: LLMConfig = {
  base_url: "",
  api_key: "",
  model: "",
};

function load(): LLMConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...defaultConfig, ...JSON.parse(raw) };
    }
  } catch {
    // ignore
  }
  return { ...defaultConfig };
}

const config = ref<LLMConfig>(load());

watch(
  config,
  (val) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(val));
  },
  { deep: true }
);

export function useLLMConfig() {
  function setConfig(cfg: Partial<LLMConfig>) {
    config.value = { ...config.value, ...cfg };
  }

  function clear() {
    config.value = { ...defaultConfig };
    localStorage.removeItem(STORAGE_KEY);
  }

  function isConfigured(): boolean {
    return Boolean(
      config.value.api_key && config.value.base_url && config.value.model
    );
  }

  return { config, setConfig, clear, isConfigured };
}
