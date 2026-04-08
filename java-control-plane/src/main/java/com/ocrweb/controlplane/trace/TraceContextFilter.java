package com.ocrweb.controlplane.trace;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

@Component
public class TraceContextFilter extends OncePerRequestFilter {
    public static final String TRACE_HEADER = "X-Trace-Id";
    private static final String W3C_TRACEPARENT_HEADER = "traceparent";
    private static final String MDC_KEY = "trace_id";

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        String traceId = resolveTraceId(request);
        RequestTraceContext.setTraceId(traceId);
        MDC.put(MDC_KEY, traceId);
        request.setAttribute(TRACE_HEADER, traceId);
        response.setHeader(TRACE_HEADER, traceId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_KEY);
            RequestTraceContext.clear();
        }
    }

    private static String resolveTraceId(HttpServletRequest request) {
        String traceId = request.getHeader(TRACE_HEADER);
        if (StringUtils.hasText(traceId)) {
            return traceId.trim();
        }
        String correlationId = request.getHeader(W3C_TRACEPARENT_HEADER);
        if (StringUtils.hasText(correlationId)) {
            return correlationId.trim();
        }
        return UUID.randomUUID().toString();
    }
}
