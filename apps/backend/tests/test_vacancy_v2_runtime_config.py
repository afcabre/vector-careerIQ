import unittest

from app.core.settings import Settings
from app.services.vacancy_v2_runtime_config import (
    default_vacancy_v2_runtime_config,
    get_vacancy_v2_runtime_config,
    normalize_vacancy_v2_runtime_config,
)


class VacancyV2RuntimeConfigTests(unittest.TestCase):
    def test_defaults_are_returned_when_no_env_override_exists(self) -> None:
        settings = Settings(vacancy_v2_runtime_config_json="")
        config = get_vacancy_v2_runtime_config(settings)
        self.assertEqual(config, default_vacancy_v2_runtime_config())

    def test_json_override_updates_step2_and_step3_temperature(self) -> None:
        settings = Settings(
            vacancy_v2_runtime_config_json=(
                "{\"step2\":{\"llm_temperature\":0.35},\"step3\":{\"llm_temperature\":0.2}}"
            )
        )
        config = get_vacancy_v2_runtime_config(settings)
        self.assertEqual(config["step2"]["llm_temperature"], 0.35)
        self.assertEqual(config["step3"]["llm_temperature"], 0.2)

    def test_invalid_json_falls_back_to_defaults(self) -> None:
        settings = Settings(vacancy_v2_runtime_config_json="{invalid-json")
        config = get_vacancy_v2_runtime_config(settings)
        self.assertEqual(config, default_vacancy_v2_runtime_config())

    def test_normalization_clamps_temperature_range(self) -> None:
        config = normalize_vacancy_v2_runtime_config(
            {
                "step2": {"llm_temperature": -1},
                "step3": {"llm_temperature": 99},
            }
        )
        self.assertEqual(config["step2"]["llm_temperature"], 0.0)
        self.assertEqual(config["step3"]["llm_temperature"], 1.0)


if __name__ == "__main__":
    unittest.main()
