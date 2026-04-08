package com.ocrweb.controlplane.trace;

public final class RequestTraceContext {
    private static final ThreadLocal<String> TRACE_ID_HOLDER = new ThreadLocal<>();

    private RequestTraceContext() {
    }

    public static void setTraceId(String traceId) {
        TRACE_ID_HOLDER.set(traceId);
    }

    public static String getTraceId() {
        return TRACE_ID_HOLDER.get();
    }

    public static void clear() {
        TRACE_ID_HOLDER.remove();
    }
}
