import { Badge, Button, FrappeUI, TextInput, Textarea } from 'frappe-ui'
import LucideStar from '~icons/lucide/star'
import type { Component, Plugin } from 'vue'

const pluginContract: Plugin = FrappeUI
const componentContracts: Component[] = [Badge, Button, TextInput, Textarea, LucideStar]

export { componentContracts, pluginContract }
