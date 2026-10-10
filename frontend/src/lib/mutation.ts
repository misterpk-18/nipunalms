import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { ApiError, errorMessage } from "@/api/client";

/** Where a finished action leaves the person: a link to the item it changed, and what happens next. */
export type ToastView = { to: string; label?: string };

/**
 * useMutation with the app's defaults: a success toast that says what happened and, when given, what happens next and a
 * "View" link to the changed item; an error toast (field errors are left to the form when `silentValidation` is set);
 * and invalidation of the given query keys.
 */
export function useApiMutation<TVars, TResult>(
  fn: (vars: TVars) => Promise<TResult>,
  options: {
    success?: string | ((result: TResult) => string);
    /** One line under the message: what happens next ("Students are told by notification"). */
    next?: string | ((result: TResult) => string);
    /** A "View" button on the toast that opens the changed item. */
    view?: ToastView | ((result: TResult) => ToastView | undefined);
    invalidate?: QueryKey[];
    onSuccess?: (result: TResult, vars: TVars) => void;
    onError?: (error: unknown) => void;
    silentValidation?: boolean;
  } = {},
) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: fn,
    onSuccess: async (result, vars) => {
      if (options.success) {
        const message = typeof options.success === "function" ? options.success(result) : options.success;
        const description = typeof options.next === "function" ? options.next(result) : options.next;
        const view = typeof options.view === "function" ? options.view(result) : options.view;
        toast.success(message, {
          ...(description ? { description } : {}),
          ...(view ? { action: { label: view.label ?? "View", onClick: () => void navigate({ to: view.to }) } } : {}),
        });
      }
      await Promise.all((options.invalidate ?? []).map((queryKey) => queryClient.invalidateQueries({ queryKey })));
      options.onSuccess?.(result, vars);
    },
    onError: (error) => {
      const validation = error instanceof ApiError && error.code === "VALIDATION_ERROR" && error.details;
      if (error instanceof ApiError && error.code === "FRESH_AUTH_REQUIRED") toast.error("Action cancelled — password confirmation is required");
      else if (!(validation && options.silentValidation)) toast.error(errorMessage(error));
      options.onError?.(error);
    },
  });
}
