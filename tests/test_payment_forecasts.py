"""Regression scenarios from Tables 5F8D50 and C206B1."""

import unittest

from mission_game.social_policy import SocialPolicy, Traits, winner
from tests.helpers import tokens
from tests.test_policy import observation


def prepared(view, traits=Traits(0, .3, .3)):
    policy = SocialPolicy(traits=traits)
    policy.memory.observe(view)
    policy.beliefs.observe(view, policy.memory)
    return policy


class PaymentForecastTests(unittest.TestCase):
    def test_outcomes_are_integer_pots_and_reproduce_the_expected_deposits(self):
        view = observation('contribute', pot=tokens(blue=2, red=1), crew_size=3)
        crew = ['p0', 'p1', 'p2']
        pledges = {'p0': tokens(blue=3), 'p1': tokens(blue=2, green=1), 'p2': tokens(blue=4)}
        view['public'].update(crew=crew, pledges=pledges)
        policy = prepared(view)
        own = tokens(red=3)
        outcomes = policy.forecast_outcomes(view, crew, own, pledges)
        mean, deposits = policy.forecast(view, crew, own, pledges)
        self.assertAlmostEqual(sum(mass for _, mass in outcomes), 1)
        self.assertEqual(deposits['p0'], own)
        for pot, mass in outcomes:
            self.assertGreater(mass, 0)
            self.assertTrue(all(type(n) is int and n >= 0 for n in pot.values()))
            self.assertLessEqual(sum(pot.values()), 13)  # Existing 3 + own 3 + others 7.
        for color in ('blue', 'red', 'green'):
            self.assertAlmostEqual(sum(pot[color] * mass for pot, mass in outcomes), mean[color])
        self.assertIn(tokens(blue=2, red=4), [pot for pot, _ in outcomes])  # Both withhold.
        self.assertIn(tokens(blue=8, red=4, green=1), [pot for pot, _ in outcomes])  # Both honor.

    def test_red_rejects_a_likely_blue_tie_despite_a_red_mean_pot(self):
        view = observation('vote', team='red', pot=tokens(blue=3, red=6), threshold=11, crew_size=4)
        crew = ['p0', 'p1', 'p2', 'p3']
        view['public'].update(crew=crew, score={'blue': 2, 'red': 2},
                              pledges={pid: tokens(blue=1 if pid == 'p3' else 2) for pid in crew})
        view['public']['players'][0]['wallet'] = 2
        policy = prepared(view)
        for pid in crew[1:]:
            policy.beliefs.players[pid]['kept'] = 100
        action = policy.choose_action(view)
        details = policy.last_decision['details']
        self.assertEqual(winner(details['forecast_pot'], 11), 'red')
        self.assertGreater(details['outcome_likelihoods']['blue'], .9)
        self.assertIn(tokens(blue=8, red=8), [s['pot'] for s in details['outcome_scenarios']])
        self.assertLess(details['objective_utility'], 0)
        self.assertFalse(action['approve'])

    def test_equal_terminal_plans_protect_blue_for_loyalist_and_contrarian(self):
        for team, objective in (('blue', 'loyalist'), ('red', 'contrarian'), ('blue', 'reliable_partner')):
            for phase in ('pledge', 'vote', 'contribute'):
                for seed in range(6):
                    with self.subTest(team=team, objective=objective, phase=phase, seed=seed):
                        view = observation(phase, team=team, objective=objective, pot=tokens(blue=6))
                        view['private']['objective']['progress'] = {'value': 2}
                        view['public'].update(crew=['p0', 'p1'], score={'blue': 2, 'red': 0},
                                              pledges={'p0': tokens(), 'p1': tokens()})
                        view['public']['players'][1]['wallet'] = 0
                        policy = SocialPolicy(seed, traits=Traits(1, .5, .3))
                        policy.choose_action(view)
                        # Even five Red would leave a Blue win, but it has no
                        # advantage over the same-cost safer Blue payment.
                        self.assertEqual(policy.last_decision['details']['planned_deposit'], tokens(blue=5))

    def test_caution_does_not_reward_retaining_tokens_in_a_certain_outcome(self):
        view = observation('contribute', threshold=4)
        view['public'].update(crew=['p0', 'p1'], pledges={'p0': tokens(), 'p1': tokens()})
        for caution in (0, 1):
            policy = prepared(view, Traits(1, caution, 0))
            smaller = policy.outcome_value(view, tokens(blue=4), tokens(blue=4), ['p0', 'p1'], tokens())
            larger = policy.outcome_value(view, tokens(blue=5), tokens(blue=5), ['p0', 'p1'], tokens())
            self.assertEqual(smaller, larger)
            self.assertEqual(policy.choose_action(view)['tokens'], tokens(blue=5))
            self.assertEqual(policy.last_decision['details']['risk_adjustment'], 0)

    def test_caution_weighs_downside_risk_without_changing_the_payment_model(self):
        view = observation('contribute')
        view['public']['score'] = {'blue': 2, 'red': 2}
        outcomes = [(tokens(blue=8), .6), (tokens(red=8), .4)]
        values = []
        for caution in (0, 1):
            policy = prepared(view, Traits(0, caution, 0))
            value, details = policy.evaluate_outcomes(view, outcomes, tokens(), ['p0'], tokens())
            self.assertAlmostEqual(details['expected_outcome_utility'], 20)
            self.assertAlmostEqual(details['outcome_likelihoods']['personal_win'], .6)
            values.append(value)
        self.assertLess(values[1], values[0])

    def test_passenger_reward_is_only_earned_in_scenarios_that_complete(self):
        view = observation('contribute', objective='passenger')
        view['public'].update(crew=['p0', 'p1'], pledges={'p0': tokens(), 'p1': tokens(blue=5)})
        policy = prepared(view)
        _, details = policy.evaluate_outcomes(view, [(tokens(blue=8), .4), (tokens(blue=3), .6)],
                                             tokens(), ['p0', 'p1'], tokens())
        self.assertAlmostEqual(details['expected_objective_incentive'], 1)
        self.assertAlmostEqual(details['condition_likelihood'], .4)

    def test_unready_saver_objects_without_asking_for_less_blue(self):
        view = observation('vote', objective='saver', pot=tokens(blue=4))
        view['public'].update(crew=['p1', 'p2'], score={'blue': 2, 'red': 0},
                              pledges={'p1': tokens(blue=4), 'p2': tokens(blue=4)})
        view['public']['players'][0]['wallet'] = 8
        action = prepared(view).choose_action(view)
        self.assertFalse(action['approve'])
        self.assertEqual(len(action['complaints']), 1)
        self.assertNotEqual(action['complaints'][0], {'modifier': 'less', 'color': 'blue'})


if __name__ == '__main__':
    unittest.main()
