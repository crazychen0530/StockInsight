import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
  },
  {
    path: '/stocks',
    name: 'stock-search',
    component: () => import('@/views/StockSearchView.vue'),
  },
  {
    path: '/stocks/:symbol',
    name: 'stock-detail',
    component: () => import('@/views/StockDetailView.vue'),
  },
  { path: '/guide', name: 'guide', component: () => import('@/views/GuideView.vue') },
  { path: '/learn', name: 'learn', component: () => import('@/views/LearnView.vue') },
  { path: '/source-settings', name: 'source-settings', component: () => import('@/views/SourceSettingsView.vue') },
  { path: '/data-status', name: 'data-status', component: () => import('@/views/DataStatusView.vue') },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: to => to.hash ? { el: to.hash } : { top: 0 },
})
