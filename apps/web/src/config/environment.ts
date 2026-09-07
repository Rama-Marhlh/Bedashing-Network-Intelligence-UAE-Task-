const requiredServerUrl = (value: string | undefined, fallback: string): string => {
  const candidate = value?.trim() || fallback;
  return new URL(candidate).toString();
};

export const serverEnvironment = {
  agentUrl: requiredServerUrl(process.env.AGENT_URL, "http://127.0.0.1:8000/ag-ui"),
} as const;
