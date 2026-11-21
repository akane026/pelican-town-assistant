import { lazy, Suspense, useState } from 'react';
import { NavLink, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import {
  BookOpen,
  CalendarDays,
  ChevronRight,
  Home,
  Menu,
  MessageCircle,
  Network,
  Plus,
  Settings as SettingsIcon,
  Sprout as SproutIcon,
} from 'lucide-react';
import { useBootstrap } from './hooks/use-workbench';
import { Loading, ErrorState } from './components/feedback';
import { Pelican } from './components/pixel-art';
import { Settings } from './components/settings';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './components/ui/dialog';
import { taskTitle } from './lib/format';
import type { ExecutionMode } from './lib/types';
import { hasApiKey } from './lib/credentials';

const ChatPage = lazy(() => import('./pages/chat-page'));
const GraphPage = lazy(() => import('./pages/graph-page'));
const PlansPage = lazy(() => import('./pages/plans-page'));
const KnowledgePage = lazy(() => import('./pages/knowledge-page'));
const links = [
  { to: '/chat', label: '农场助手', icon: MessageCircle },
  { to: '/graph', label: '物品图谱', icon: Network },
  { to: '/plans', label: '我的计划', icon: CalendarDays },
];

function Navigation({ close, settings }: { close: () => void; settings: () => void }) {
  const { data } = useBootstrap();
  return (
    <>
      <Link className="brand" to="/chat" onClick={close}>
        <Pelican />
        <span>
          鹈鹕镇助手<small>你的农场小帮手</small>
        </span>
      </Link>
      <Link className="new-chat town-button" to="/chat" onClick={close}>
        <Plus size={21} /> 新的对话
      </Link>
      <nav aria-label="主要导航">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={close}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={21} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="recent">
        <h2>最近对话</h2>
        {data?.tasks.length ? (
          data.tasks.slice(0, 12).map((task) => (
            <NavLink
              to={`/chat/${task.task_id}`}
              key={task.task_id}
              onClick={close}
              title={taskTitle(task)}
              className="history-item"
            >
              <MessageCircle size={16} />
              <span>{taskTitle(task)}</span>
            </NavLink>
          ))
        ) : (
          <p>
            第一篇农场笔记，
            <br />
            从一个问题开始。
          </p>
        )}
      </div>
      <div className="sidebar-bottom">
        <NavLink
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          to="/knowledge"
          onClick={close}
        >
          <BookOpen size={20} />
          知识管理
        </NavLink>
        <button
          className="nav-item"
          onClick={() => {
            close();
            settings();
          }}
        >
          <SettingsIcon size={20} />
          设置
        </button>
        <small className="local-note">
          <span /> 本机工作台
        </small>
      </div>
    </>
  );
}

export default function App() {
  const boot = useBootstrap();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(() => !hasApiKey());
  const [mode, setMode] = useState<ExecutionMode>('candidate_diagnostic');
  const title =
    [...links, { to: '/knowledge', label: '知识管理' }].find((link) =>
      location.pathname.startsWith(link.to),
    )?.label || '农场助手';
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <aside className="sidebar">
        <Navigation close={() => {}} settings={() => setSettingsOpen(true)} />
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="menu-button icon-button"
              aria-label="打开导航"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={23} />
            </button>
            <Home size={21} className="home-icon" />
            <ChevronRight size={16} />
            <span>{title}</span>
          </div>
          <button className="condition-button" onClick={() => setSettingsOpen(true)}>
            <SettingsIcon size={17} />
            <span>游戏条件</span>
            <small>设置</small>
          </button>
        </header>
        {boot.data && !boot.data.snapshot && (
          <div className="connection-note">
            <SproutIcon size={16} />
            <span>农场知识库还在等待导入</span>
            <Link to="/knowledge">查看准备步骤</Link>
          </div>
        )}
        <main id="main-content" tabIndex={-1}>
          {boot.isLoading ? (
            <Loading text="正在连接本机工作台…" />
          ) : boot.error ? (
            <ErrorState error={boot.error} retry={() => void boot.refetch()} />
          ) : (
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/" element={<Navigate to="/chat" replace />} />
                <Route path="/chat" element={<ChatPage mode={mode} />} />
                <Route path="/chat/:taskId" element={<ChatPage mode={mode} />} />
                <Route path="/graph" element={<GraphPage />} />
                <Route path="/plans" element={<PlansPage />} />
                <Route path="/knowledge" element={<KnowledgePage />} />
                <Route path="*" element={<Navigate to="/chat" replace />} />
              </Routes>
            </Suspense>
          )}
        </main>
      </div>
      <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogContent className="town-dialog mobile-nav">
          <DialogHeader className="sr-only">
            <DialogTitle>农场导航</DialogTitle>
            <DialogDescription>前往助手、图谱、计划和知识管理。</DialogDescription>
          </DialogHeader>
          <Navigation close={() => setMobileOpen(false)} settings={() => setSettingsOpen(true)} />
        </DialogContent>
      </Dialog>
      <Settings
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        mode={mode}
        setMode={setMode}
      />
    </div>
  );
}
