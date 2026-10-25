/**
 * Authentication context.
 *
 * Provides the current user, a login helper, a register helper, and a
 * logout helper to the entire component tree.  State is initialised from
 * localStorage so a page refresh keeps the user logged in.
 *
 * Usage:
 *   const { user, login, logout, isLoading } = useAuth();
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  authApi,
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from "../services/api";
import type {
  LoginRequest,
  RegisterRequest,
  UserResponse,
} from "../types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthContextValue {
  /** The authenticated user, or null when logged out. */
  user: UserResponse | null;
  /** True while the initial token-validation fetch is in flight. */
  isLoading: boolean;
  /** Log in with email + password; stores the token and sets the user. */
  login: (credentials: LoginRequest) => Promise<void>;
  /** Register a new account, then log in automatically. */
  register: (details: RegisterRequest) => Promise<void>;
  /** Clear the stored token and user state. */
  logout: () => void;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: if a token exists in localStorage, validate it with /auth/me.
  // This restores the session after a page refresh.
  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setIsLoading(false);
      return;
    }

    authApi
      .me()
      .then((me) => setUser(me))
      .catch(() => {
        // Token is expired or invalid — clean it up silently.
        clearStoredToken();
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    const { access_token } = await authApi.login(credentials);
    setStoredToken(access_token);
    const me = await authApi.me();
    setUser(me);
  }, []);

  const register = useCallback(async (details: RegisterRequest) => {
    // Register creates the account; then log in to get a token.
    await authApi.register(details);
    await authApi
      .login({ email: details.email, password: details.password })
      .then(async ({ access_token }) => {
        setStoredToken(access_token);
        const me = await authApi.me();
        setUser(me);
      });
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/** Consume the auth context. Must be used inside <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
