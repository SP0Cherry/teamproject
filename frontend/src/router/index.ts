import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import Home from "../views/Home.vue";
import Login from "../views/Login.vue";
import Register from "../views/Register.vue";
import Notifications from "../views/Notifications.vue";
import NotificationConfirm from "../views/NotificationConfirm.vue";
import Schedule from "../views/Schedule.vue";
import TodoAdd from "../views/TodoAdd.vue";
import QA from "../views/QA.vue";
import Groups from "../views/Groups.vue";
import GroupDetail from "../views/GroupDetail.vue";
import WorkspaceLayout from "../layouts/WorkspaceLayout.vue";
import NotFound from "../views/NotFound.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: Login },
    { path: "/register", name: "register", component: Register },
    {
      path: "/",
      component: WorkspaceLayout,
      children: [
        { path: "", name: "home", component: Home },
        { path: "notifications", name: "notifications", component: Notifications },
        { path: "notifications/:id", name: "notification-confirm", component: NotificationConfirm },
        { path: "schedule", name: "schedule", component: Schedule },
        { path: "todos/add", name: "todo-add", component: TodoAdd },
        { path: "qa", name: "qa", component: QA },
        { path: "groups", name: "groups", component: Groups },
          { path: "groups/:id", name: "group-detail", component: GroupDetail },
      ],
    },
    { path: "/:pathMatch(.*)*", name: "not-found", component: NotFound },
  ],
});

router.beforeEach(async (to, _from, next) => {
  const auth = useAuthStore();
  const publicPaths = ["/login", "/register"];

  if (!auth.isAuthenticated && !publicPaths.includes(to.path)) {
    // Restore the session from the HttpOnly refresh cookie before forcing a
    // fresh login (the access token lives only in memory, SEC-06).
    const restored = await auth.tryRefresh();
    if (!restored) {
      return next({ path: "/login", query: { redirect: to.fullPath } });
    }
  }
  if (auth.isAuthenticated && publicPaths.includes(to.path)) {
    return next("/");
  }
  next();
});

export default router;
