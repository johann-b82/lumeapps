import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/auth/useAuth";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

type LoginFormValues = z.infer<typeof loginSchema>;

/**
 * /login page per 29-UI-SPEC §"Login Card".
 *
 * - Static "KPI Dashboard" wordmark (no /api/settings fetch — login page is unauthed).
 * - Inline error "Invalid email or password" on failed signIn; no toast (D-06).
 * - Never reveals which field was wrong.
 * - On success, AuthGate handles navigation to /.
 */
export function LoginPage() {
  const { signIn } = useAuth();
  const [loginError, setLoginError] = useState(false);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);

  useEffect(() => {
    let revoke: string | null = null;
    fetch("/api/settings/logo/public")
      .then((res) => {
        if (!res.ok) return;
        return res.blob();
      })
      .then((blob) => {
        if (blob) {
          revoke = URL.createObjectURL(blob);
          setLogoUrl(revoke);
        }
      })
      .catch(() => {});
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, []);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const {
    handleSubmit,
    formState: { isSubmitting },
  } = form;

  const onSubmit = async (values: LoginFormValues) => {
    setLoginError(false);
    try {
      await signIn(values.email, values.password);
    } catch {
      setLoginError(true);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <Card className="w-full max-w-sm border border-border shadow-sm">
        <CardHeader>
          {logoUrl && (
            <img
              src={logoUrl}
              alt="Logo"
              className="mx-auto h-16 w-16 object-contain mb-2"
            />
          )}
        </CardHeader>
        <CardContent>
          <h1 className="text-2xl font-semibold text-center text-foreground mb-6">
            Sign in
          </h1>
          <Form {...form}>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        autoFocus
                        autoComplete="email"
                        placeholder="email@example.com"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        autoComplete="current-password"
                        placeholder="Password"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button
                type="submit"
                className="w-full"
                size="default"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Signing in…
                  </>
                ) : (
                  "Sign in"
                )}
              </Button>
              {loginError && (
                <p className="text-[13px] text-destructive text-center mt-2">
                  Invalid email or password
                </p>
              )}
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
