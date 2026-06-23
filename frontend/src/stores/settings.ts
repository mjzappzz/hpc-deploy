import { defineStore } from 'pinia'
import { getSettings } from '@/api/settings'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    default_ssh_key_name: '',
  }),

  actions: {
    async load() {
      try {
        const res = await getSettings()
        this.default_ssh_key_name = res.data.default_ssh_key_name
      } catch {
        // Fall back to defaults
      }
    },
  },
})
