import { StrictMode, useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { Stations } from './Stations';
import { Batteries } from './Batteries';
import { Devices } from './Devices';
import { Reservations } from './Reservations';

type Role = 'ADMIN' | 'CUSTOMER' | 'TECHNICIAN';
type User = { id: string; username: string; role: Role; state: 'ACTIVE' | 'LOCKED' | 'INACTIVE'; version: number; created_at: string };
const roles: Record<Role, string> = { ADMIN: 'Quản trị viên', CUSTOMER: 'Khách hàng', TECHNICIAN: 'Kỹ thuật viên' };
const states = { ACTIVE: 'Hoạt động', LOCKED: 'Đã khóa', INACTIVE: 'Ngừng sử dụng' };

function App() {
  const [view, setView] = useState<'stations' | 'accounts' | 'batteries' | 'devices' | 'reservations'>('stations');
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const api = useCallback(async (path: string, method = 'GET', data?: unknown, mutationKey?: string) => {
    const response = await fetch(path, { method, headers: {
      'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(mutationKey ? { 'Idempotency-Key': mutationKey } : {}),
    }, ...(data !== undefined ? { body: JSON.stringify(data) } : {}) });
    const result = await response.json();
    if (!response.ok) {
      if (response.status === 401 && path !== '/v1/auth/login') { setToken(null); setUser(null); }
      const messages: Record<string, string> = {
        INVALID_CREDENTIALS: 'Thông tin đăng nhập không đúng hoặc tài khoản không khả dụng.',
        LOGIN_LIMITED: 'Đã vượt giới hạn đăng nhập. Vui lòng thử lại sau 15 phút.',
        SESSION_REVOKED: 'Phiên đã kết thúc. Vui lòng đăng nhập lại.',
        SESSION_INVALID: 'Phiên đã hết hạn. Vui lòng đăng nhập lại.',
        LAST_ADMIN: 'Cần giữ ít nhất một quản trị viên đang hoạt động.',
        USER_REFERENCED: 'Tài khoản đang giữ pin, có phân công hoặc giao dịch cần xử lý.',
        VERSION_CONFLICT: 'Dữ liệu đã được cập nhật. Hãy tải lại danh sách.',
        RESOURCE_CONFLICT: 'Mã định danh đã tồn tại hoặc dữ liệu đang được sử dụng.',
        EVIDENCE_REQUIRED: 'Chưa có đủ bằng chứng thiết bị mới, hợp lệ để thực hiện thao tác.',
        ACTIVE_TRANSACTION: 'Tài nguyên đang bị giữ hoặc liên quan đến giao dịch chưa kết thúc.',
        UNRESOLVED_ALERTS: 'Còn cảnh báo chưa xử lý; ACK không phải đã giải quyết.',
        BATTERY_CUSTOMER_HELD: 'Không thể ngừng pin đang do khách giữ.',
        STATE_CONFLICT: 'Trạng thái hiện tại không cho phép thao tác này.',
        FORBIDDEN: 'Bạn không có quyền thực hiện thao tác này.',
      };
      throw new Error(messages[result.code] ?? `API từ chối thao tác (${result.code ?? response.status}). Hãy kiểm tra quyền, phiên bản và điều kiện trạng thái.`);
    }
    if (path.includes('/telemetry') && response.headers.has('X-Battery-Available')) {
      result.assessment = { available: response.headers.get('X-Battery-Available') === 'true', at: response.headers.get('X-Battery-Assessed-At'), limits: (response.headers.get('X-BMS-Limits') ?? '').split(',').map(Number) };
    }
    if (response.headers.has('X-Dashboard-Poll-Seconds')) result.poll_interval_seconds = Number(response.headers.get('X-Dashboard-Poll-Seconds'));
    return result;
  }, [token]);

  async function loadUsers() {
    let cursor: string | null = null;
    const all: User[] = [];
    do {
      const page: { items: User[]; next_cursor: string | null } = await api('/v1/users?limit=100' + (cursor ? `&cursor=${cursor}` : ''));
      all.push(...page.items); cursor = page.next_cursor;
    } while (cursor);
    setUsers(all);
  }

  useEffect(() => {
    if (token && user?.role === 'ADMIN') loadUsers().catch(e => setError(e.message));
    if (!token) setUsers([]);
  }, [token, user?.role]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setNotice(''); setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await api('/v1/auth/login', 'POST', { username: form.get('username'), password: form.get('password') });
      setToken(result.access_token); setUser(result.user); setView('stations');
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function signOut() {
    setError('');
    try {
      await api('/v1/auth/logout', 'POST', undefined, crypto.randomUUID());
      setToken(null); setUser(null); setView('stations'); setNotice('Bạn đã đăng xuất an toàn.');
    } catch (e) { setError((e as Error).message); }
  }

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget;
    const form = new FormData(element); setBusy(true); setError(''); setNotice('');
    try {
      await api('/v1/users', 'POST', { username: form.get('username'), password: form.get('password'), role: form.get('role') }, crypto.randomUUID());
      element.reset(); await loadUsers(); setNotice('Đã tạo tài khoản.');
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function changeUser(target: User, changes: Partial<Pick<User, 'role' | 'state'>>) {
    setBusy(true); setError(''); setNotice('');
    try {
      await api(`/v1/users/${target.id}`, 'PATCH', { expected_version: target.version, ...changes }, crypto.randomUUID());
      if (target.id === user?.id) { setToken(null); setUser(null); setNotice('Quyền tài khoản đã thay đổi. Vui lòng đăng nhập lại.'); }
      else { await loadUsers(); setNotice('Đã cập nhật tài khoản và thu hồi các phiên cũ.'); }
    } catch (e) { setError((e as Error).message); await loadUsers().catch(() => {}); } finally { setBusy(false); }
  }

  return <div className="app-shell">
    <header><a href="/" className="brand"><span className="brand-icon">ϟ</span><span>ĐỔI PIN<span className="brand-sub">MẠNG LƯỚI THÔNG MINH</span></span></a><span className="environment"><i/> Môi trường mô phỏng</span></header>
    <main>
      <div className="intro"><span className="eyebrow">CỔNG THÔNG TIN</span><h1>{user ? `Xin chào, ${user.username}.` : 'Một tài khoản.\nKết nối cả mạng lưới.'}</h1><p>{user ? 'Quản lý phiên truy cập và tài khoản trong phạm vi quyền của bạn.' : 'Đăng nhập để truy cập không gian dành cho khách hàng, quản trị viên và kỹ thuật viên.'}</p></div>
      {error && <div className="message error" role="alert">{error}</div>}
      {notice && <div className="message success" role="status">{notice}</div>}
      {!user ? <div className="login-layout"><section className="card login-card"><span className="eyebrow">CHÀO MỪNG TRỞ LẠI</span><h2>Đăng nhập</h2><form onSubmit={signIn}><label>Tên tài khoản<input name="username" autoComplete="username" required maxLength={100} autoFocus/></label><label>Mật khẩu<input name="password" type="password" autoComplete="current-password" required maxLength={256}/></label><button className="primary" disabled={busy}>{busy ? 'Đang xác thực…' : 'Đăng nhập →'}</button></form><p className="hint">Sử dụng tài khoản đã được quản trị viên cấp.</p></section><aside><span className="large-bolt">ϟ</span><h2>Đúng người.<br/>Đúng quyền truy cập.</h2><p>Mỗi vai trò có một không gian riêng. Thông tin tài khoản được bảo vệ xuyên suốt phiên làm việc.</p><div className="role-tags">{Object.values(roles).map(role => <span key={role}>{role}</span>)}</div></aside></div> : <>
        <section className="card profile"><div><span className="eyebrow">PHIÊN CỦA BẠN</span><h2>{roles[user.role]}</h2><p><span className="badge">{states[user.state]}</span> <span className="hint">@{user.username}</span></p></div><button onClick={signOut}>Đăng xuất</button></section>
        <nav className="module-nav">{user.role !== 'TECHNICIAN' && <button onClick={() => setView('reservations')}>QR/RFID và giữ tài nguyên</button>}<button onClick={() => setView('stations')}>Trạm và ngăn tủ</button>{user.role !== 'CUSTOMER' && <><button onClick={() => setView('batteries')}>Pin và BMS</button><button onClick={() => setView('devices')}>Thiết bị và IoT</button></>}{user.role === 'ADMIN' && <button onClick={() => setView('accounts')}>Tài khoản</button>}</nav>
        {view === 'reservations' ? <Reservations api={api} role={user.role}/> : view === 'stations' ? <Stations api={api} role={user.role}/> : view === 'batteries' ? <Batteries api={api} role={user.role}/> : view === 'devices' ? <Devices api={api} role={user.role}/> : user.role === 'ADMIN' ? <section className="admin-grid"><div className="card"><span className="eyebrow">CẤP QUYỀN TRUY CẬP</span><h2>Tạo tài khoản</h2><form onSubmit={createUser}><label>Tên tài khoản<input name="username" required minLength={3} maxLength={100} autoComplete="off"/></label><label>Mật khẩu ban đầu<input name="password" type="password" required minLength={12} maxLength={256} autoComplete="new-password"/><small>Tối thiểu 12 ký tự.</small></label><label>Vai trò<select name="role">{Object.entries(roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button className="primary" disabled={busy}>Tạo tài khoản</button></form></div><div className="card user-list"><div className="section-heading"><div><span className="eyebrow">QUẢN TRỊ</span><h2>Danh sách tài khoản</h2></div><button disabled={busy} onClick={() => loadUsers().catch(e => setError(e.message))}>Tải lại</button></div><div className="table-scroll"><table><thead><tr><th>Tài khoản</th><th>Vai trò</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>{users.map(target => <tr key={target.id}><td><strong>{target.username}</strong></td><td><select aria-label={`Vai trò của ${target.username}`} value={target.role} disabled={busy} onChange={event => { if (confirm(`Đổi vai trò của ${target.username}? Các phiên hiện tại sẽ kết thúc.`)) changeUser(target, { role: event.target.value as Role }); }} >{Object.entries(roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td><td><span className={target.state === 'ACTIVE' ? 'badge' : 'badge muted'}>{states[target.state]}</span></td><td><button disabled={busy} onClick={() => { if (confirm(`${target.state === 'ACTIVE' ? 'Khóa' : 'Mở khóa'} tài khoản ${target.username}?`)) changeUser(target, { state: target.state === 'ACTIVE' ? 'LOCKED' : 'ACTIVE' }); }}>{target.state === 'ACTIVE' ? 'Khóa' : 'Mở khóa'}</button></td></tr>)}</tbody></table></div></div></section> : <section className="card"><h2>Thông tin truy cập</h2><p>{user.role === 'CUSTOMER' ? 'Bạn đang đăng nhập bằng tài khoản khách hàng của mình.' : 'Bạn đang đăng nhập bằng tài khoản kỹ thuật viên. Quyền thao tác được giới hạn theo trạm được phân công.'}</p></section>}
      </>}
    </main><footer><span>ĐỔI PIN · Hệ thống quản lý trạm</span><span>Dữ liệu và thiết bị mô phỏng</span></footer>
  </div>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
