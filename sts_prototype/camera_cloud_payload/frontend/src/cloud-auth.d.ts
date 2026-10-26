declare module '*.mjs' {
  export function accessToken(storage: Storage): string | null;
  export const config: {apiUrl: string};
}
