import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import KanbanBoardView from '@/views/KanbanBoardView.vue'
import TaskComposerView from '@/views/TaskComposerView.vue'
import TaskDetailView from '@/views/TaskDetailView.vue'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: { name: 'compose' },
  },
  {
    path: '/compose',
    name: 'compose',
    component: TaskComposerView,
  },
  {
    path: '/board',
    name: 'board',
    component: KanbanBoardView,
  },
  {
    path: '/tasks/:taskId',
    name: 'task-detail',
    component: TaskDetailView,
    props: true,
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: { name: 'compose' },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
