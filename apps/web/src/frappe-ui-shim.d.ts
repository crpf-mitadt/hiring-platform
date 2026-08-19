import type { App, DefineComponent } from 'vue'

type FrappeComponent = DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>

export const Badge: FrappeComponent
export const Button: FrappeComponent
export const Textarea: FrappeComponent
export const TextInput: FrappeComponent
export const FrappeUI: {
  install(_app: App): void
}
