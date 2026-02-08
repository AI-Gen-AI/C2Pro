'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Zap, User, Shield, Crown } from 'lucide-react';

export function DevRoleSwitcher() {
  const { setDemoRole, userRole } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Only show in development and when mounted
  if (!isMounted || !setDemoRole) {
    return null;
  }

  const roleConfig = {
    user: { label: 'User', icon: User, color: 'bg-blue-500' },
    tenant_admin: { label: 'Tenant Admin', icon: Shield, color: 'bg-purple-500' },
    c2pro_admin: { label: 'C2Pro Admin', icon: Crown, color: 'bg-amber-500' },
  };

  const currentConfig = roleConfig[userRole as keyof typeof roleConfig] || roleConfig.user;

  const handleRoleChange = (role: 'user' | 'tenant_admin' | 'c2pro_admin') => {
    setDemoRole(role);
    setIsOpen(false);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            size="lg"
            className="rounded-full shadow-lg gap-2 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white"
          >
            <Zap className="h-4 w-4" />
            Dev Mode
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>Switch Demo Role</DropdownMenuLabel>
          <DropdownMenuSeparator />

          {(Object.entries(roleConfig) as Array<[string, typeof currentConfig]>).map(
            ([role, config]) => (
              <DropdownMenuItem
                key={role}
                onClick={() => handleRoleChange(role as 'user' | 'tenant_admin' | 'c2pro_admin')}
                className={`cursor-pointer gap-2 ${
                  userRole === role ? 'bg-muted font-medium' : ''
                }`}
              >
                <config.icon className="h-4 w-4" />
                {config.label}
                {userRole === role && <span className="ml-auto text-xs">✓</span>}
              </DropdownMenuItem>
            )
          )}

          <DropdownMenuSeparator />

          <DropdownMenuItem disabled className="text-xs text-muted-foreground">
            Current: {currentConfig.label}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
