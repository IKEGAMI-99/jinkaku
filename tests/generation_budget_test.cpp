#include "../app/src/main/cpp/generation_budget.h"
#include <cassert>
#include <iostream>

int main() {
    GenerationBudget b;
    // Regression: 250-token normal reply must not stop at 250 thought tokens.
    b.reset(true, 250);
    b.observe("<|channel>thought");
    for (int i = 1; i < 250; ++i) b.observe("reason ");
    assert(b.thought == 250 && !b.done() && !b.needs_final());
    for (int i = 250; i < 512; ++i) b.observe("reason ");
    assert(b.needs_final() && b.answer == 0 && b.closer() == "<channel|>");
    b.force_final();
    for (int i = 0; i < 249; ++i) b.observe("answer ");
    assert(!b.done());
    b.observe("end");
    assert(b.done() && b.answer == 250 && b.thought == 512 && b.forced);

    for (int limit : {96, 120, 250, 600, 1024}) {
        b.reset(false, limit);
        for (int i = 0; i < limit; ++i) {
            assert(!b.done());
            b.observe("text");
        }
        assert(b.done() && b.thought == 0 && b.answer == limit);
    }
    b.reset(true, 120);
    b.observe("<|chan"); b.observe("nel>thought"); b.observe("reason");
    b.observe("<chan"); b.observe("nel|>");
    assert(b.phase == GenerationBudget::Phase::Answer && b.answer == 0);
    b.observe("visible");
    assert(b.answer == 1 && !b.forced);

    b.reset(true, 120);
    b.observe(" \n"); b.observe("Direct answer");
    assert(b.thought == 0 && b.answer == 2);
    b.reset(true, 120);
    b.seed_prompt("<|turn>model\n<|channel>thought\n");
    assert(b.in_thought() && b.thought == 0);
    b.observe("reason"); b.observe("<channel|>");
    assert(b.answer == 0 && b.thought == 2);

    b.reset(true, 250);
    b.seed_prompt("system <think> example, user message ends here");
    assert(!b.in_thought());
    b.observe("<think>");
    assert(b.closer() == "</think>");
    b.observe("reason</think>answer");
    assert(b.answer == 1);
    b.reset(true, 250);
    b.observe("<|channel>analysis");
    assert(b.closer() == "<|channel>final");
    b.observe("hidden"); b.observe("<|channel>final");
    assert(b.answer == 0);

    // Very small remaining context: recognize delimiter before forcing it closed.
    b.reset(true, 120, 0);
    assert(!b.needs_final()); b.observe("<think>"); assert(b.needs_final());
    b.reset(true, 120);
    b.observe("<|think|>"); b.observe("hidden"); b.observe("</think>");
    assert(!b.in_thought() && b.answer == 0);
    std::cout << "Generation budget tests passed\n";
}
