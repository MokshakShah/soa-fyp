"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Admin, getStoredAdmin, clearToken } from "@/lib/api/client";
import { getMe } from "@/lib/api/auth";

interface AuthContextType {
  admin: Admin | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  setAdmin: (admin: Admin | null) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextType>({
  admin: null,
  isLoading: true,
  isAuthenticated: false,
  setAdmin: () => {},
  signOut: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [admin, setAdminState] = useState<Admin | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = getStoredAdmin();
    if (stored) {
      setAdminState(stored);
      // Verify token is still valid
      getMe()
        .then((a) => setAdminState(a))
        .catch(() => {
          clearToken();
          setAdminState(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const setAdmin = useCallback((a: Admin | null) => {
    setAdminState(a);
  }, []);

  const signOut = useCallback(() => {
    clearToken();
    setAdminState(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        admin,
        isLoading,
        isAuthenticated: !!admin,
        setAdmin,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
