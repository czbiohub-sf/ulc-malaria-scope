import sys
import time
import numpy
from matplotlib import pyplot
try:
    from PyQt5 import QtCore, QtWidgets
except:
    from PyQt4 import QtCore, QtGui


class StampTimer(QtCore.QTimer):
    signal_quit = QtCore.pyqtSignal()

    def __init__(self, number_of_samples, precise=False, *args, **kwargs):
        super(StampTimer, self).__init__(*args, **kwargs)
        if precise:
            try:
                self.setTimerType(QtCore.Qt.PreciseTimer)
                print('using precise timer (PyQt5)')
            except:
                print('precise timer not available (PyQt4)')
        self.number_of_samples = number_of_samples
        self.stamps_ms = []
        self.timeout.connect(self.stamp)

    def start(self):
        self.stamps_ms = []
        super(StampTimer, self).start()

    def stamp(self):
        # Save a timestamp (use clock() instead of time())
        self.stamps_ms.append(1e3 * time.clock())
        # Quit when we reach the specified number of samples
        if len(self.stamps_ms) == self.number_of_samples:
            self.stop()
            self.signal_quit.emit()


try:
    app = QtWidgets.QApplication(sys.argv)
except:
    app = QtGui.QApplication(sys.argv)

# Parameters
number_of_intervals = 100
intervals_requested_ms = range(1, 10)
intervals_requested_ms.extend(list(range(10, 60, 2)))
intervals_requested_ms.extend(list(range(60, 200, 10)))
intervals_requested_ms.append(1000)

# Variables
intervals_measured_ms = numpy.zeros(
    (number_of_intervals, len(intervals_requested_ms)), float)

# Run
timer = StampTimer(number_of_samples=number_of_intervals+1, precise=False)
timer.signal_quit.connect(app.quit)
for index, interval_requested_ms in enumerate(intervals_requested_ms):
    # For each interval in the list, we run the timer until we obtain 
    # the specified number of samples
    timer.setInterval(interval_requested_ms)
    timer.start()
    app.exec_()
    # Calculate statistics
    intervals_measured_ms[:, index] = numpy.diff(timer.stamps_ms)
    median_ms = numpy.median(intervals_measured_ms[:, index])
    max_ms = numpy.max(intervals_measured_ms[:, index])
    min_ms = numpy.min(intervals_measured_ms[:, index])
    # Add to plot
    print('requested: {} ms, '
          'measured: median(min/max) {:.1f} ({:.2f}/{:.2f}) ms'.format(
        interval_requested_ms, median_ms, min_ms, max_ms)
        )
    pyplot.plot(interval_requested_ms, median_ms, 'ok')
    pyplot.plot([interval_requested_ms]*2, [min_ms, max_ms], '-k')

# Plot result
pyplot.plot([0, 1000], [0, 1000], 'k--')
pyplot.xscale('log', nonposx='clip')
pyplot.yscale('log', nonposy='clip')
pyplot.xlabel('interval requested [ms]')
pyplot.ylabel(
    'interval measured [ms] (median, n={})'.format(number_of_intervals))
pyplot.show()