import { createContext, useContext } from "react";

export type ToastKind = "success" | "info" | "error";
export type ShowToast = (message: string, kind?: ToastKind) => void;

export const ToastContext = createContext<ShowToast>(() => {});

/** Show a short message at the bottom of the screen (e.g. "Saved."). */
export const useToast = (): ShowToast => useContext(ToastContext);
