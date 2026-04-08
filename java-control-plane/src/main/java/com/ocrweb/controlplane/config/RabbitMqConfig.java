package com.ocrweb.controlplane.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.Map;

@Configuration
public class RabbitMqConfig {

    @Bean
    public DirectExchange commandExchange(RabbitMqProperties properties) {
        return new DirectExchange(properties.getExchange(), true, false);
    }

    @Bean
    public DirectExchange deadLetterExchange(RabbitMqProperties properties) {
        return new DirectExchange(properties.getDeadLetterExchange(), true, false);
    }

    @Bean
    public Queue commandQueue(RabbitMqProperties properties) {
        return new Queue(
                properties.getQueue(),
                true,
                false,
                false,
                Map.of("x-dead-letter-exchange", properties.getDeadLetterExchange())
        );
    }

    @Bean
    public Queue deadLetterQueue(RabbitMqProperties properties) {
        return new Queue(properties.getDeadLetterQueue(), true);
    }

    @Bean
    public Binding commandBinding(Queue commandQueue, DirectExchange commandExchange, RabbitMqProperties properties) {
        return BindingBuilder.bind(commandQueue).to(commandExchange).with(properties.getRoutingKey());
    }

    @Bean
    public Binding deadLetterBinding(Queue deadLetterQueue, DirectExchange deadLetterExchange, RabbitMqProperties properties) {
        return BindingBuilder.bind(deadLetterQueue).to(deadLetterExchange).with(properties.getDeadLetterQueue());
    }

    @Bean
    public Jackson2JsonMessageConverter jackson2JsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
