from drivers.driver_factory import DriverFactory


class DriverManager:
    def __init__(self, config):
        self.config = config
        self.driver = None

    def start_driver(self):
        self.driver = DriverFactory.create_driver(self.config)
        return self.driver

    def stop_driver(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
