import { createApp } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppCritters from '../../src/components/AppCritters.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
})
await router.push('/')
createApp(AppCritters).use(router).mount('#app')
