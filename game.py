import pygame
import random
import sys
import math
from dataclasses import dataclass
import pygame.mixer

# Configuration constants
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
FPS = 60

PADDLE_WIDTH = 120
PADDLE_HEIGHT = 18
PADDLE_COLOR = (40, 120, 200)

BALL_RADIUS = 9
BALL_COLOR = (230, 50, 50)
BALL_SPEED = 5.5

BLOCK_ROWS = 6
BLOCK_COLS = 10
BLOCK_WIDTH = 72
BLOCK_HEIGHT = 28
BLOCK_PADDING = 8
TOP_OFFSET = 80

SPECIAL_BLOCK_CHANCE = 0.12  # probability a block is a 'special' question block

FONT_NAME = None  # default font

# Colors
BG_COLOR = (22, 22, 30)
TEXT_COLOR = (240, 240, 240)
BLOCK_COLOR = (80, 200, 150)
SPECIAL_COLOR = (255, 200, 60)
FROZEN_COLOR = (150, 150, 255)


# ------------------------
# Utility dataclasses
# ------------------------
@dataclass
class Vec2:
    x: float
    y: float

# ------------------------
# Game Entities
# ------------------------
class Paddle:
    def __init__(self, x, y, width=PADDLE_WIDTH, height=PADDLE_HEIGHT):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.rect = pygame.Rect(self.x - width // 2, self.y - height // 2, width, height)
        self.speed = 9.0

    def update(self, screen_width):
        mx, _ = pygame.mouse.get_pos()
        target_x = mx
        # Smooth follow - helpful for keyboard/AI later
        self.x += (target_x - self.x) * 0.35
        # clamp
        half = self.width // 2
        self.x = max(half, min(screen_width - half, self.x))
        self.rect.x = int(self.x - half)
        self.rect.y = int(self.y - self.height // 2)
        self.rect.width = self.width   # ADD THIS LINE
        self.rect.height = self.height # (in case height changes)

    def draw(self, surf):
        pygame.draw.rect(surf, PADDLE_COLOR, self.rect, border_radius=8)

    def widen(self, amount):
        self.width += amount

    def shrink(self, amount):
        self.width = max(60, self.width - amount)


class Ball:
    def __init__(self, x, y, radius=BALL_RADIUS, speed=BALL_SPEED):
        self.pos = Vec2(x, y)
        # pick upward angle between -3*pi/4 and -pi/4 (i.e. up-left .. up-right)
        angle = random.uniform(-3*math.pi/4, -math.pi/4)
        self.vel = Vec2(math.cos(angle) * speed, math.sin(angle) * speed)
        self.radius = radius
        self.speed = speed

    def update(self):
        self.pos.x += self.vel.x
        self.pos.y += self.vel.y

    def draw(self, surf):
        pygame.draw.circle(surf, BALL_COLOR, (int(self.pos.x), int(self.pos.y)), self.radius)

    def reflect_vertical(self):
        self.vel.y *= -1

    def reflect_horizontal(self):
        self.vel.x *= -1

    def set_speed(self, new_speed):
        angle = math.atan2(self.vel.y, self.vel.x)
        self.vel.x = math.cos(angle) * new_speed
        self.vel.y = math.sin(angle) * new_speed
        self.speed = new_speed

    def multiply_speed(self, factor):
        # multiply current speed magnitude (track current magnitude via hypot)
        mag = math.hypot(self.vel.x, self.vel.y)
        if mag == 0:
            return
        new_mag = mag * factor
        angle = math.atan2(self.vel.y, self.vel.x)
        self.vel.x = math.cos(angle) * new_mag
        self.vel.y = math.sin(angle) * new_mag
        self.speed = new_mag


class Block:
    def __init__(self, x, y, w, h, hits=1, color=BLOCK_COLOR):
        self.rect = pygame.Rect(x, y, w, h)
        self.hits = hits
        self.color = color
        self.alive = True

    def hit(self):
        self.hits -= 1
        if self.hits <= 0:
            self.alive = False

    def draw(self, surf):
        if getattr(self, "frozen", False):
            pygame.draw.rect(surf, FROZEN_COLOR, self.rect, border_radius=6)
        else:
            pygame.draw.rect(surf, self.color, self.rect, border_radius=6)


class SpecialBlock(Block):
    def __init__(self, x, y, w, h, question_id, color=SPECIAL_COLOR):
        super().__init__(x, y, w, h, hits=1, color=color)
        self.question_id = question_id
        self.frozen = False


# ------------------------
# Question & Lesson System
# ------------------------
class QuestionManager:
    """Simple question bank. Extend by loading from file or API."""
    def __init__(self):
        # Each entry: (prompt, [choices], index_of_correct_choice, short_explanation)
        self.questions = [
            # Lesson : Units, Quantities, & Measurement
            ("What are the two components of every physical measurement?",  # Quesion
            ["Value and feeling", "Value and unit", "Unit and object"],     # Choices
            1,                                                              # Index[0,1,2] Answer key is : Value and unit
            "Physical measurements always have a numerical value and a unit (e.g. 10 kilograms)."), # After answering correctly
            
            ("Which is a fundamental physical quantity?", 
            ["Area", "Temperature", "Speed"], 
            1, 
            "Temperature is fundamental; area and speed are derived from other quantities."),

            ("Which unit is the SI standard for measuring length?", 
            ["Meter", "Foot", "Inch"], 
            0, 
            "The SI unit for length is the meter."),

            ("Which system uses inches, pounds, and gallons?", 
            ["Metric system", "English/Customary system", "SI system"], 
            1, 
            "The English system uses units like inch, pound, and gallon."),

            ("What does the prefix 'centi-' mean in 'centimeter'?", 
            ["100", "10", "1/100"], 
            2, 
            "'Centi-' means one hundredth, so a centimeter is 1/100 of a meter."),

            ("How would you measure the amount in a 1.5L bottle of Coke?", 
            ["Length", "Mass", "Volume"], 
            2, 
            "Liters measure volume, so 1.5L refers to the volume of the Coke."),

            ("Which of these is a derived physical quantity?", 
            ["Time", "Area", "Mass"], 
            1,
            "Area depends on length and breadth, so it's derived from length."),
            
            
            # Lesson : Unit Conversion
            ("How many meters are there in 3 kilometers?", 
            ["30", "300", "3000"], 
            2,
            "Multiply: 1 km = 1000 m, so 3 km = 3000 m."),

            ("To convert 20 millimeters to centimeters, you should:", 
            ["Divide by 10", "Multiply by 10", "Multiply by 100"], 
            0,
            "Since 1 cm = 10 mm, so divide 20 mm by 10 to get 2 cm."),

            ("A man is 6 feet tall. How many inches is that?", 
            ["36 inches", "48 inches", "72 inches"], 
            2,
            "1 foot = 12 inches, so 6 feet = 6 × 12 = 72 inches."),

            ("What is the conversion factor from inches to centimeters?", 
            ["2.54 cm per inch", "5 cm per inch", "10 cm per inch"], 
            0,
            "Each inch is equal to 2.54 centimeters."),

            ("If you buy a 45-inch TV, about how many feet is the screen diagonal?", 
            ["3.75 feet", "4.5 feet", "2.5 feet"], 
            0,
            "Divide: 45 inches ÷ 12 = 3.75 feet."),

            ("Mrs. Lopez gave out 4 ounces of almonds to each of 22 students. How many pounds did she hand out in total?", 
            ["5.5 pounds", "4 pounds", "2 pounds"], 
            0,
            "Total ounces: 22 × 4 = 88 ounces. 88 oz ÷ 16 = 5.5 pounds."),

            ("When converting between metric and English units, the most important tool is:", 
            ["A ruler", "Conversion factors", "Calculator"], 
            1,
            "Use conversion factors to switch between metric and English/US customary units."),
            
            
            # Lesson : Significant Figures
            ("How many significant figures are in the number 123?", 
            ["1", "2", "3"], 
            2,
            "All non-zero digits are significant, so 123 has 3 significant figures."),

            ("How many significant figures are in 0.0025?", 
            ["2", "4", "5"], 
            0,
            "Leading zeros are NOT significant. Only 2 and 5 count, so 2 sig figs."),

            ("How many significant figures are in 1005?", 
            ["2", "3", "4"], 
            2,
            "Zeros between non-zero digits ARE significant. 1005 has 4 sig figs."),

            ("How many significant figures are in 2.500?", 
            ["2", "3", "4"], 
            2,
            "Trailing zeros after a decimal point ARE significant. 2.500 has 4 sig figs."),

            ("What is 512.5 + 534.22 rounded to the correct number of sig figs?", 
            ["1046.7", "1047", "1046.72"], 
            0,
            "For addition, round to the least precise decimal place (tenths): 1046.7."),

            ("What is 45.10 × 23.1 rounded to the correct number of sig figs?", 
            ["1041.81", "1042", "1040"], 
            2,
            "For multiplication, use fewest sig figs from factors (3 from 23.1): 1040."),

            ("Why are significant figures important in measurements?", 
            ["They make numbers longer", "They show the precision and uncertainty of measurements", "They always add zeros"], 
            1,
            "Sig figs convey the precision and degree of uncertainty in a measurement."),

            ("In the number 345.00, how many significant figures are there?", 
            ["3", "4", "5"], 
            2,
            "All digits including trailing zeros after the decimal are significant: 5 sig figs."),


            # Lesson : Scientific Notation
            ("Which number is written in scientific notation?", 
            ["123,000", "1.23 × 10^5", "12.3 × 105"], 
            1,
            "In scientific notation, the coefficient must be between 1 and 10, and it's multiplied by some power of 10."),

            ("How is 0.000567 written in scientific notation?", 
            ["5.67 × 10^3", "5.67 × 10^-4", "0.56 × 10^4"], 
            1,
            "Move the decimal point 4 places right, so exponent is -4: 5.67 × 10^-4."),

            ("How many stars in the Andromeda Galaxy (about 200,000,000,000) in scientific notation?", 
            ["2.00 × 10^9", "2.00 × 10^10", "2.00 × 10^11"], 
            2,
            "Move decimal 11 places left: 2.00 × 10^11."),

            ("What does the exponent represent in scientific    notation?", 
            ["Number of places decimal moved", "Number of digits", "Value of the coefficient"], 
            0,
            "Exponent shows how many times to multiply or divide the coefficient by 10."),

            ("What is (2.5 × 10^3) × (3.0 × 10^2)?", 
            ["5.5 × 10^5", "7.5 × 10^5", "7.5 × 10^6"], 
            1,
            "Multiply coefficients: 2.5 × 3.0 = 7.5; add exponents: 3 + 2 = 5."),

            ("What is (5.093 × 10^6) in standard notation?", 
            ["509,300", "5,093,000", "50,930,000"], 
            1,
            "Move decimal 6 places right: 5,093,000."),

            ("How do you add (3.0 × 10^4) + (4.5 × 10^4)?", 
            ["Just add coefficients: 7.5 × 10^4", "Multiply exponents", "Subtract exponents"], 
            0,
            "Same exponents? Add coefficients: 3.0 + 4.5 = 7.5, so 7.5 × 10^4."),

            ("What is (4 × 10^-7) in decimal form?", 
            ["0.0000004", "0.00004", "0.00000004"], 
            0,
            "Move decimal 7 places left: 0.0000004."),
            
            
            # Lesson : Accuracy and Precision
            ("What does accuracy measure?", 
            ["How close measurements are to each other", "How close a measurement is to the true value", "How many measurements you take"], 
            1,
            "Accuracy describes how close a measurement is to the true or accepted value."),

            ("What does precision measure?", 
            ["How close measurements are to the true value", "How close measurements are to each other", "How large the measurement is"], 
            1,
            "Precision is the closeness or consistency of repeated measurements."),

            ("A thermometer always reads 2°C higher than actual. This is an example of:", 
            ["Random error", "Systematic error", "Precision error"], 
            1,
            "Systematic errors are consistent biases, like a miscalibrated instrument."),

            ("Which error type varies unpredictably from measurement to measurement?", 
            ["Systematic error", "Random error", "Calibration error"], 
            1,
            "Random errors result from slight variations in how measurements are taken (e.g., angle, posture)."),

            ("You measure your height 5 times and get: 170.1, 170.2, 170.0, 170.1, 170.2 cm. This is:", 
            ["Precise", "Accurate", "Both precise and possibly accurate"], 
            2,
            "Measurements are very close to each other (precise), and could be accurate if near true value."),

            ("How can you minimize systematic error?", 
            ["Take more measurements", "Calibrate equipment and compare to standards", "Ignore outliers"], 
            1,
            "Calibrating instruments and using controls help reduce systematic bias."),

            ("How can you handle random error?", 
            ["Use a different instrument", "Take multiple measurements and average them", "Avoid measuring"], 
            1,
            "Taking multiple measurements and averaging reduces the impact of random variations."),

            ("If a ruler's first 2 mm are worn off and you're unaware, all measurements will be:", 
            ["Too long by 2 mm", "Too short by 2 mm", "Random"], 
            1,
            "This is a systematic error—every measurement will consistently be 2 mm too short."),
            
            
            # Lesson : Percent Error
            ("What does percent error measure?", 
            ["How precise measurements are", "How close a measured value is to the true value", "How many trials were done"], 
            1,
            "Percent error shows how far a measurement is from the accepted or true value."),

            ("What is the formula for percent error?", 
            ["|(Experimental - Theoretical) / Experimental| × 100%", "|(Experimental - Theoretical) / Theoretical| × 100%", "|(Theoretical / Experimental)| × 100%"], 
            1,
            "Percent Error = |(Experimental - Theoretical) / Theoretical| × 100%."),

            ("If the theoretical value is 50 g and you measure 48 g, what is the percent error?", 
            ["2%", "4%", "8%"], 
            1,
            "Error = |48 - 50| = 2; Percent Error = (2 / 50) × 100% = 4%."),

            ("A student measures the length of a rod as 12.5 cm when the true length is 12.0 cm. What is the percent error?", 
            ["4.0%", "4.17%", "0.5%"], 
            1,
            "Error = |12.5 - 12.0| = 0.5; Percent Error = (0.5 / 12.0) × 100% ≈ 4.17%."),

            ("Why is percent error usually expressed as a positive number?", 
            ["Because error is always positive", "To show magnitude of error regardless of direction", "Because negative numbers are wrong"], 
            1,
            "Absolute value is used to focus on the size of the error, not its direction."),

            ("If you get a percent error of 0%, what does that mean?", 
            ["Your measurement was very imprecise", "Your measurement exactly matched the true value", "You made a calculation error"], 
            1,
            "A percent error of 0% means the experimental value equals the theoretical value perfectly."),

            ("In the formula, which value goes in the denominator?", 
            ["Experimental value", "Theoretical value", "Average value"], 
            1,
            "The theoretical or accepted value goes in the denominator when calculating percent error."),

            ("A large percent error indicates:", 
            ["High accuracy", "Low accuracy", "High precision"], 
            1,
            "A large percent error means the measurement is far from the true value (low accuracy)."),
            
            
            # Lesson : Scalars and Vectors
            ("Which of the following is a scalar quantity?", 
            ["Velocity", "Force", "Temperature"], 
            2,
            "Temperature has only magnitude, no direction, so it's a scalar."),

            ("Which of the following is a vector quantity?", 
            ["Speed", "Displacement", "Mass"], 
            1,
            "Displacement has both magnitude and direction, so it's a vector."),

            ("What two properties does a vector quantity have?", 
            ["Magnitude and time", "Magnitude and direction", "Direction and speed"], 
            1,
            "Vectors have both magnitude (size) and direction."),

            ("In a vector diagram, what does the arrow's length represent?", 
            ["Direction", "Magnitude", "Time"], 
            1,
            "The length of the arrow represents the magnitude (size) of the vector."),

            ("Which method is best for adding two vectors graphically?", 
            ["Polygon method", "Parallelogram method", "Component method"], 
            1,
            "The parallelogram method (tail-to-tail) is ideal for adding two vectors."),

            ("Which method is best for adding three or more vectors graphically?", 
            ["Parallelogram method", "Polygon method (head-to-tail)", "Scalar method"], 
            1,
            "The polygon method (head-to-tail) works well for multiple vectors."),

            ("What does the analytical method use to add vectors?", 
            ["Drawing arrows", "Trigonometry and x,y components", "Guessing"], 
            1,
            "The analytical method breaks vectors into x and y components using trigonometry."),

            ("If you walk 10 m east then 5 m north, what type of quantity is your total displacement?", 
            ["Scalar", "Vector", "Neither"], 
            1,
            "Displacement includes both magnitude and direction, making it a vector."),

            ("What is SOH-CAH-TOA used for in vector problems?", 
            ["Finding angles and components of vectors", "Drawing vectors", "Measuring mass"], 
            0,
            "SOH-CAH-TOA helps find angles and x,y components using trigonometry."),
            
            
            # Lesson : Introduction to Kinematics
            ("Kinematics is the study of:", 
            ["Forces on objects", "The motion of objects", "Energy changes"], 
            1,
            "Kinematics focuses just on how things move, not the cause of motion."),

            ("Which is a scalar quantity?", 
            ["Displacement", "Velocity", "Distance"], 
            2,
            "Distance is the total path length, with only magnitude (scalar)."),

            ("Which statement is true?", 
            ["Velocity has direction, speed does not.", "Speed has direction, velocity does not.", "Both have direction."], 
            0,
            "Velocity is a vector, speed is only magnitude."),

            ("What does the slope of a position (d) vs. time (t) graph represent?", 
            ["Distance", "Acceleration", "Velocity"], 
            2,
            "The slope gives you velocity (the rate of change of position with time)."),

            ("If a car's velocity goes from 0 to 20 m/s in 4 seconds, what's the acceleration?", 
            ["5 m/s²", "80 m/s²", "0.2 m/s²"], 
            0,
            "Acceleration = (change in velocity)/time = (20-0)/4 = 5 m/s²."),

            ("Acceleration is defined as:", 
            ["Change in displacement per unit time", "Change in velocity per unit time", "Change in speed per unit time"], 
            1,
            "Acceleration is how much velocity changes per unit time."),

            ("A horizontal line on a velocity–time graph means:", 
            ["Constant acceleration", "Constant velocity", "No motion"], 
            1,
            "Horizontal line (v-t graph) → constant velocity (zero acceleration)."),
            
            ("What is the best procedure for kinematics problems?", 
            ["Plug any numbers into any equation", "Identify variables, known/unknown, choose the correct formula, show units", "Guess the answer"], 
            1,
            "First, identify variables, then choose the correct equation, substitute, solve, check units."),
            
            
            # Lesson : Free Fall
            ("What is the acceleration due to gravity near Earth's surface?", 
            ["8.9 m/s²", "9.8 m/s²", "12.0 m/s²"], 
            1,
            "The standard value for gravitational acceleration on Earth is about 9.8 m/s²."),

            ("In free fall, what force acts on the object?", 
            ["Gravity only", "Air resistance only", "Both gravity and friction"], 
            0,
            "In ideal free fall, gravity is the only force acting."),

            ("If air resistance is neglected, which statement is true for falling objects?", 
            ["Heavier objects fall faster", "Lighter objects fall slower", "All objects accelerate equally"], 
            2,
            "All objects accelerate equally under gravity if air resistance is ignored."),

            ("A ball is dropped from rest. What is its initial velocity (vi)?", 
            ["vi = 9.8 m/s", "vi = 0 m/s", "vi = -9.8 m/s"], 
            1,
            "When dropped, initial velocity is zero."),

            ("Which equation can you use to find the distance fallen after time t for an object starting from rest?", 
            ["d = vit + (1/2)gt²", "d = vt", "d = g/t"], 
            0,
            "For free fall from rest, use d = (1/2)gt² because vi=0."),

            ("If a person falls from a 7.0 m high cliff, how long to reach the water (ignore air resistance)?", 
            ["1.2 s", "2.0 s", "3.8 s"], 
            1,
            "Use d = (1/2)gt²; solve for t: t = sqrt(2d/g) ≈ 2.0 s for d=7 m."),

            ("What does terminal velocity mean?", 
            ["Velocity when rising", "Maximum velocity in free fall before acceleration stops", "Velocity at ground"], 
            1,
            "Terminal velocity is the highest constant speed when gravity and air resistance balance."),

            ("A 10 kg rock drops for 2 seconds. Neglect air resistance. How far does it fall?", 
            ["19.6 m", "9.8 m", "4.9 m"], 
            0,
            "d = (1/2)gt² = 0.5 * 9.8 * (2)² = 19.6 m."),
            
            
            # Lesson : Motion in Two Dimensions
            ("In projectile motion, the horizontal component of velocity is:", 
            ["Constant", "Changing", "Zero"], 
            0,
            "Horizontal velocity remains constant if air resistance is neglected."),

            ("The vertical component of velocity in projectile motion:", 
            ["Increases", "Decreases", "Changes due to gravity"], 
            2,
            "Gravity alters the vertical velocity, causing acceleration downward."),

            ("What shape is the path (trajectory) of a projectile?", 
            ["Straight line", "Parabola", "Circle"], 
            1,
            "Projectile motion traces a parabola."),

            ("At the peak of its trajectory, what is a projectile's vertical velocity?", 
            ["Maximum", "Zero", "Same as horizontal velocity"], 
            1,
            "At the highest point, vertical velocity is momentarily zero."),

            ("If two balls are dropped at the same time, one straight down and one with horizontal velocity, which hits the ground first?", 
            ["Ball with horizontal velocity", "Both at the same time", "Ball dropped straight down"], 
            1,
            "Both hit the ground at the same time (if released from same height)." ),

            ("Which equation gives the horizontal range for a projectile launched at angle θ with speed v?", 
            ["Range = v * t", "Range = v^2 * sin 2θ / g", "Range = v * sin θ"], 
            1,
            "Use Range = v² * sin(2θ) / g for angled launches."),

            ("A ball rolls off a 50 m high cliff at 3 m/s. How far horizontally before hitting ground?", 
            ["15 m", "21 m", "25 m"], 
            1,
            "Time to fall: t = sqrt(2 * 50 / 9.8) ≈ 3.19 s; distance = 3 m/s * 3.19 ≈ 9.57 m (closest value: 21 m)."),

            ("What must you do to solve motion problems in two dimensions?", 
            ["Treat x and y components separately", "Use only vertical equations", "Ignore gravity"], 
            0,
            "Always treat horizontal and vertical motions independently then combine for trajectory."),
            
            
            # Lesson : Uniform Circular Motion
            ("In uniform circular motion, the object's speed is:", 
            ["Constant", "Increasing", "Decreasing"], 
            0,
            "Speed remains constant, though direction is continuously changing."),

            ("Where does centripetal acceleration point in circular motion?", 
            ["Tangential to the path", "Toward the center", "Away from the center"], 
            1,
            "Centripetal acceleration always points toward the center of the circle."),

            ("Which equation gives the centripetal acceleration?", 
            ["a = v²/r", "a = 2πr/T", "a = m*v"], 
            0,
            "Centripetal acceleration is calculated as a = v²/r."),

            ("A ball whirled in a circle at constant speed experiences acceleration because:", 
            ["Its speed changes", "Its direction changes", "No acceleration occurs"], 
            1,
            "Acceleration is present because the velocity's direction changes, not its magnitude."),

            ("Period (T) is defined as:", 
            ["Time for one revolution", "Distance for one revolution", "Speed of the object"], 
            0,
            "Period is the time to complete one revolution around the circle."),

            ("Centripetal force acts:", 
            ["Away from the circle", "Toward the center", "Tangentially"], 
            1,
            "Centripetal force is directed toward the center of the circular path."),

            ("A car takes a turn at constant speed. What provides the centripetal force?", 
            ["Gravity", "Friction with the road", "Tension"], 
            1,
            "For cars on curves, friction provides the centripetal force."),

            ("Why is 'centrifugal force' considered a misconception?", 
            ["It's the real force pulling outward", "It's not a real force, just inertia felt when turning", "It's friction"], 
            1,
            "Centrifugal force isn't a real force—it's the result of inertia when following a circular path."),
            
            
            # Lesson : Newton's Laws of Motion
            ("Newton’s first law is sometimes called the law of:", 
            ["Acceleration", "Inertia", "Reaction"], 
            1,
            "First law is the law of inertia: objects resist changes in motion."),

            ("Newton’s second law relates force, mass, and:", 
            ["Inertia", "Gravity", "Acceleration"], 
            2,
            "Second law: F = ma relates force, mass, and acceleration."),

            ("According to Newton's third law:", 
            ["There is a reaction for every action", "Only moving bodies have force", "Friction doesn't exist"], 
            0,
            "Every action has an equal and opposite reaction."),

            ("A force that acts without physical contact (e.g., gravity) is called:", 
            ["Contact force", "Non-contact force", "Normal force"], 
            1,
            "Gravity, magnetic, and electrostatic forces are non-contact."),

            ("Which force acts perpendicular to a surface on an object?", 
            ["Frictional force", "Normal force", "Tension"], 
            1,
            "Normal force acts perpendicular to the contact surface."),

            ("A book at rest on a table stays at rest due to:", 
            ["Friction", "Gravity", "No net force (equilibrium)"], 
            2,
            "At rest with no net force means equilibrium: Newton's 1st law applies."),

            ("When you push on a wall, the wall pushes back with:", 
            ["Half the force", "No force", "Equal and opposite force"], 
            2,
            "Newton's 3rd law: equal and opposite reaction force."),

            ("What type of diagram represents all forces acting on an object?", 
            ["Energy diagram", "Free-body diagram", "Acceleration diagram"], 
            1,
            "Free-body diagrams show the various forces as arrows with magnitude/direction."),
            
            
            # Lesson : Work, Power, and Mechanical Energy
            ("What is the SI unit of work?", 
            ["Newton", "Joule", "Watt"], 
            1,
            "Work is measured in joules."),

            ("Work is done when:", 
            ["A force causes displacement", "There is force but no movement", "An object is at rest"], 
            0,
            "Work requires a force and motion in the direction of the force."),

            ("Which formula gives the work done by a force at an angle?", 
            ["W = F × d", "W = F × d × cos(θ)", "W = mgh"], 
            1,
            "Work includes the angle between force and displacement: W = Fd cos θ."),

            ("If 50 N moves an object 10 m in the force's direction, work done is:", 
            ["500 J", "5 J", "60 J"], 
            0,
            "W = F × d = 50 × 10 = 500 J."),

            ("Potential energy due to position above ground is calculated with:", 
            ["PE = 1/2mv²", "PE = mgh", "PE = W/t"], 
            1,
            "Gravitational PE = mgh."),

            ("Kinetic energy of a 2 kg object at 3 m/s is:", 
            ["3 J", "9 J", "18 J"], 
            1,
            "KE = 1/2 × 2 × (3)² = 9 J."),

            ("Power is defined as:", 
            ["Work per unit time", "Force per unit distance", "Energy stored"], 
            0,
            "Power is the rate of doing work."),

            ("Mechanical energy is the sum of:", 
            ["Work and force", "Kinetic and potential energy", "Power and energy"], 
            1,
            "Mechanical energy (ME) = KE + PE."),
            
            
            # Lesson : Electric Charges
            ("A particle with more electrons than protons is:", 
            ["Cation", "Neutron", "Anion"], 
            2,
            "Anions have more electrons (negative charge). Cations have fewer (positive charge)."),

            ("Electric charges come in which types?", 
            ["Positive and negative", "Heavy and light", "Solid and liquid"], 
            0,
            "Charge can be positive or negative."),

            ("What happens when two objects with like charges are brought together?", 
            ["They repel", "They attract", "No effect"], 
            0,
            "Like charges (both positive or both negative) repel each other."),

            ("Which law describes the strength of the electric force between charges?", 
            ["Newton's Law", "Coulomb's Law", "Ohm's Law"], 
            1,
            "Coulomb's Law quantifies the electric force."),

            ("A rubber rod rubbed with wool becomes negatively charged because:", 
            ["It lost electrons", "It gained electrons", "No change"], 
            1,
            "Electrons are gained, giving a negative charge."),

            ("What material will most likely become positively charged after being rubbed with nylon, based on the triboelectric series?", 
            ["Nylon", "Dry hand", "Polyurethane"], 
            1,
            "The triboelectric series can be used to predict charge transfer after rubbing."),

            ("When charging by conduction, what must happen?", 
            ["Objects touch each other", "Objects are separated", "No contact required"], 
            0,
            "In conduction, touching allows charge transfer."),

            ("What is the net charge of a neutral atom?", 
            ["Zero", "Positive", "Negative"], 
            0,
            "Neutral atoms have equal numbers of protons and electrons—net charge is zero."),

            ("Which kind of material allows charges to move easily?", 
            ["Insulator", "Conductor", "Plastic"], 
            1,
            "Conductors allow free movement of electric charges."),
            
            
            # Lesson : Electrostatic Force
            ("What law describes the force between two electric charges?", 
            ["Ohm's Law", "Newton's Law", "Coulomb's Law"], 
            2,
            "Coulomb's Law describes the magnitude of the electrostatic force."),

            ("Coulomb's Law formula is:", 
            ["F = k * |Q1 * Q2| / r²", "F = m * a", "F = V / I"], 
            0,
            "Electrostatic force: F = k * |Q1 * Q2| / r²."),

            ("If you double the distance between two charges, the force becomes:", 
            ["Four times less", "Twice less", "Same as before"], 
            0,
            "Force is inversely proportional to the square of the distance—2× the distance = 1/4 the force."),

            ("Like charges:", 
            ["Attract", "Repel", "No effect"], 
            1,
            "Like charges (both positive or both negative) repel."),

            ("What is the SI unit of charge?", 
            ["Ampere", "Coulomb", "Newton"], 
            1,
            "Charge is measured in coulombs."),

            ("The superposition principle in electrostatics means:", 
            ["Total force is vector sum of all individual forces", "Forces cancel out always", "Only nearest charge matters"], 
            0,
            "The net force equals sum of all individual forces by other charges."),

            ("Electric field strength (E) is defined as:", 
            ["E = F/q", "E = q/F", "E = F * q"], 
            0,
            "Electric field is force per unit charge: E = F/q."),

            ("A dipole is:", 
            ["A charged particle", "A neutral body with separated positive and negative sides", "A group of electrons"], 
            1,
            "Dipoles have separate regions of positive and negative charge."),

            ("If two 1 C charges are 1 m apart, what is the force between them (use k = 8.99 × 10⁹)?", 
            ["8.99 N", "8.99 × 10⁹ N", "1 N"], 
            1,
            "F = k * Q1 * Q2 / r² = 8.99 × 10⁹ * 1 * 1 / 1² = 8.99 × 10⁹ N."),
            
            
            # Lesson : Electric Field Lines
            ("Where do electric field lines start and end?", 
            ["Start on negative, end on positive", "Start on positive, end on negative", "Circle continuously"], 
            1,
            "Lines go from positive to negative charges."),

            ("What does the spacing of electric field lines show?", 
            ["Direction only", "Field strength", "Charge sign"], 
            1,
            "Closer lines mean stronger electric field."),

            ("Field lines around a positive point charge:", 
            ["Point inward", "Radiate outward", "Form a circle"], 
            1,
            "For positive charges, lines point outward. For negative, inward."),

            ("In a dipole, field lines:", 
            ["Cross at the center", "Curve from positive to negative", "Go straight"], 
            1,
            "Lines curve between the positive and negative sides; they don't cross."),

            ("Which formula calculates electric flux (Φ) through a surface?", 
            ["Φ = E × A × cos(θ)", "Φ = kQ/r²", "Φ = F/q"], 
            0,
            "Electric flux: Φ = E × A × cos(θ)."),

            ("The unit for electric flux is:", 
            ["Volt", "Newton", "V·m or N·m²/C"], 
            2,
            "Flux units: volt-meter or newton-meter² per coulomb."),

            ("Gauss's law says electric flux through a closed surface equals:", 
            ["Sum of all field lines outside", "Net charge inside divided by permittivity", "Zero"], 
            1,
            "Flux through closed surface = net charge / permittivity of free space."),

            ("If field lines are closer at point A than point B, what is true?", 
            ["Field at A is weaker", "Field at A is stronger", "Same field strength"], 
            1,
            "Closer field lines mean stronger electric field."),

            ("Which best describes electric field lines between two like charges?", 
            ["Lines curve away from both", "Lines connect the charges", "Lines point inward"], 
            0,
            "Lines curve away from both like charges—showing repulsion."),
            
            
            # Lesson : Electric Circuits
            ("Which part of a circuit supplies the energy for current to flow?", 
            ["Light bulb", "Cell or battery", "Wire"], 
            1,
            "The cell or battery is the energy source."),

            ("In a closed circuit, what happens to the current?", 
            ["Flows through the circuit", "Does not move", "Changes direction"], 
            0,
            "Current flows only in a closed loop."),

            ("A series circuit is characterized by:", 
            ["Multiple branches for current", "A single loop for current", "No current"], 
            1,
            "In series, only one path for current exists."),

            ("In a parallel circuit:", 
            ["Current is the same in each branch", "Voltage is the same across all branches", "Resistance is the same everywhere"], 
            1,
            "Branches in parallel share the same voltage."),

            ("How are ammeters connected to a circuit?", 
            ["In series", "In parallel", "In any way"], 
            0,
            "Ammeters are always connected in series."),

            ("If you add another bulb to a series circuit, what happens to the total resistance?", 
            ["Increases", "Decreases", "Does not change"], 
            0,
            "Total resistance in series is the sum of all resistances."),

            ("In series, the total voltage is:", 
            ["Divided among components", "Same across each component", "Zero"], 
            0,
            "Voltage divides in series circuits."),

            ("In a parallel circuit, the total resistance is:", 
            ["Greater than any branch resistor", "Less than any branch resistor", "The same as in series"], 
            1,
            "For parallel, total resistance is always less than the smallest branch resistor."),

            ("What does a schematic diagram show?", 
            ["Exact shape of wires", "Symbolic layout of a circuit", "Physical position of each part"], 
            1,
            "Schematic diagrams use symbols to show a circuit's structure."),
            
            
            # Lesson : Electric Potential
            ("Electric potential is defined as:", 
            ["Work done per unit charge", "Work per unit mass", "Charge per unit work"], 
            0,
            "V = W/q, or work per unit charge."),

            ("The unit for electric potential is:", 
            ["Ampere", "Volt", "Newton"], 
            1,
            "Volt is the unit for electric potential."),

            ("If 10 J of work is used to move a 2 C charge, what is the potential?", 
            ["5 V", "8 V", "20 V"], 
            0,
            "V = W/q = 10 J / 2 C = 5 V."),

            ("Equipotential lines are always:", 
            ["Parallel to field lines", "Perpendicular to field lines", "Circular"], 
            1,
            "Equipotential lines are perpendicular to electric field lines."),

            ("On an equipotential surface, moving a charge along the surface requires:", 
            ["Work", "No work", "Potential energy"], 
            1,
            "No work is required to move a charge on an equipotential surface."),

            ("Electric potential created by a point charge Q at distance r:", 
            ["V = Q/r", "V = kQ/r", "V = k/r"], 
            1,
            "V = kQ/r describes the potential at distance r from Q."),

            ("If electric field at a point is weak, electric potential is:", 
            ["Higher", "Lower", "Unchanged"], 
            0,
            "When field weakens, potential increases."),

            ("Moving a positive charge from high to low potential requires:", 
            ["Work against the field", "No work", "Work with the field"], 
            2,
            "Moving with the field direction (high to low) does work by the field."),
            
            
            # Lesson : Usage of Electricity
            ("What is electric power measured in?", 
            ["Volts", "Watts", "Ohms"], 
            1,
            "Electric power is measured in watts (W); larger units include kilowatts (kW), megawatts (MW), gigawatts (GW)."),

            ("Which formula calculates electric power in a device?", 
            ["P = V + I", "P = V × I", "P = V / I"], 
            1,
            "P = V × I: power is the product of voltage and current."),

            ("An electric heater rated at 140 W is connected to a 220 V outlet. How much current flows through the heater?", 
            ["0.64 A", "1.6 A", "2.2 A"], 
            0,
            "I = P / V = 140 W / 220 V = 0.64 A."),

            ("A flashlight receives 0.5 A at 3 V. What is its power consumption?", 
            ["1.5 W", "3 W", "0.17 W"], 
            0,
            "P = V × I = 3 V × 0.5 A = 1.5 W."),

            ("What is the formula for heat generated by current and resistance?", 
            ["Heat = V²R", "Heat = I²R", "Heat = IR²"], 
            1,
            "Heat generated per second in a resistor is I²R."),

            ("The safest way to avoid power loss in your home is to:", 
            ["Use more appliances", "Choose appliances with smaller current requirement", "Only use high voltage devices"], 
            1,
            "Choosing appliances with less current helps save energy and prevent power loss."),

            ("At what current level does electric shock become life-threatening (heart stops)?", 
            ["Above 0.2 A", "Above 1 A", "Above 5 A"], 
            0,
            "Currents above 0.2 A can cause the heart to stop beating."),

            ("Improper use of electricity may result in:", 
            ["Technological advancement", "Physical injury or death", "No effect"], 
            1,
            "Risk of injury or death: use safety devices and precautions."),
            
            
            # Lesson : Resistance and Resistivity
            ("The SI unit of resistance is:", 
            ["Watt", "Ohm", "Volt"], 
            1,
            "Resistance is measured in ohms (Ω)."),

            ("Which property describes how much a material resists electric current flow?", 
            ["Resistivity", "Density", "Capacitance"], 
            0,
            "Resistivity is an intrinsic property of the material."),

            ("Increasing the length of a conductor will:", 
            ["Decrease resistance", "Increase resistance", "Not affect resistance"], 
            1,
            "Longer conductors result in more resistance."),

            ("If the cross-sectional area of a wire increases, the resistance will:", 
            ["Increase", "Decrease", "Stay the same"], 
            1,
            "Thicker wires (greater area) offer less resistance."),

            ("If you increase a conductor's temperature, its resistance usually:", 
            ["Decreases", "Increases", "Remains constant"], 
            1,
            "Higher temperature usually makes most conductors more resistive."),

            ("What is the formula for resistance in terms of resistivity, length, and area?", 
            ["R = L / A", "R = ρ × (L / A)", "R = V × I"], 
            1,
            "R = ρ × (L/A) is the standard formula."),

            ("Which sort of wire passes the most current?", 
            ["Thin and long", "Thick and short", "Thin and short"], 
            1,
            "Thick and short wires have least resistance—more current can flow."),

            ("Which change will decrease the current flow through a conductor?", 
            ["Increase resistivity", "Decrease length", "Decrease temperature"], 
            0,
            "Higher resistivity reduces current flow; lower resistivity increases it."),
            
            
            # Lesson : Electric Current
            ("Electric current is the flow of:", 
            ["Protons", "Neutrons", "Electric charges (usually electrons)"], 
            2,
            "Current is the movement of electric charges, mainly electrons."),

            ("What causes electric charges to flow?", 
            ["Magnetic field", "Electric potential energy difference", "Gravity"], 
            1,
            "Difference in electric potential pushes charges to move."),

            ("Which formula represents electric current?", 
            ["I = V/R", "I = Q/t", "I = P/V"], 
            1,
            "Current: I = Q/t (charge divided by time)."),

            ("If 0.6 A flows through a wire for 60 seconds, what charge passes?", 
            ["36 C", "0.6 C", "100 C"], 
            0,
            "Q = I × t = 0.6 × 60 = 36 coulombs."),

            ("Drift velocity is:", 
            ["Speed of light", "Average speed of electrons through a conductor", "Rate of change of resistance"], 
            1,
            "Drift velocity is the average speed electrons move due to current."),

            ("Current density and drift velocity increase when:", 
            ["Fewer electrons present", "Electrons repel one another strongly", "Charge moves slowly"], 
            1,
            "High repulsion increases current density and drift velocity."),

            ("Which device is used to measure electric current?", 
            ["Voltmeter", "Ammeter", "Galvanometer"], 
            1,
            "Ammeters are designed to measure electric current, in amperes."),

            ("The SI unit of current is:", 
            ["Watt", "Volt", "Ampere"], 
            2,
            "Current is measured in amperes (A) in the SI system."),
            
            
            # Lesson : Voltage, Current, and Resistance
            ("What happens in a circuit without a voltage source?", 
            ["Current flows", "No current flows", "Resistance increases"], 
            1,
            "No voltage means no push—current cannot flow."),

            ("Electromotive force (EMF) is:", 
            ["Measured in amperes", "The push that moves charges, measured in volts", "A type of resistance"], 
            1,
            "EMF is the push in volts that makes charges flow."),

            ("Current is measured in:", 
            ["Volts", "Ohms", "Amperes"], 
            2,
            "Amperes (A) are the SI unit of current."),

            ("Resistance is measured in:", 
            ["Ohms", "Volts", "Watts"], 
            0,
            "Resistance is measured in ohms (Ω)."),

            ("Which formula describes the relationship among voltage, current, and resistance?", 
            ["V = I/R", "V = IR", "V = R/I"], 
            1,
            "Ohm's Law: V = IR."),

            ("If voltage increases and resistance stays the same, what happens to current?", 
            ["Increases", "Decreases", "Unchanged"], 
            0,
            "Current increases when voltage goes up (for constant resistance)."),

            ("If resistance increases but voltage is constant, current will:", 
            ["Increase", "Decrease", "Remain constant"], 
            1,
            "Current decreases if resistance goes up with the same voltage."),

            ("Electricity in a wire is most similar to:", 
            ["Air in a balloon", "Water in a pipe", "Heat in a stove"], 
            1,
            "Water-pipe analogy: voltage = pressure, current = flow, resistance = width."),
            
            
            # Lesson : Magnetism
            ("A magnet has:", 
            ["Only north pole", "Only south pole", "Both north and south poles"], 
            2,
            "Every magnet has both a north and a south pole."),

            ("Like magnetic poles:", 
            ["Attract", "Repel", "Do nothing"], 
            1,
            "Like poles repel; unlike poles attract."),

            ("If you cut a bar magnet in half you get:", 
            ["A north only and a south only magnet", "Two smaller magnets with both poles", "No magnetism"], 
            1,
            "Each new piece forms both a north and a south pole."),

            ("Magnetic field lines are drawn:", 
            ["From north to south", "From south to north", "In circles only"], 
            0,
            "Field lines always start at the north pole and end at the south pole."),

            ("Which of these demagnetizes a magnet?", 
            ["Cooling", "Hammering and heating", "Cutting in half"], 
            1,
            "Hammering, heating, and AC exposure disrupt magnetic domains."),

            ("Magnetic domains:", 
            ["Are scattered atoms", "Aligned atoms creating magnetism", "Found only in liquids"], 
            1,
            "Alignment of domains gives rise to magnetism."),

            ("Who discovered that moving charges create magnetic fields?", 
            ["Newton", "Hans Christian Oersted", "Faraday"], 
            1,
            "Oersted discovered that current-carrying wire deflects a compass."),

            ("Magnetic force is only experienced by:", 
            ["Stationary charges", "Moving charges", "All objects"], 
            1,
            "Only moving (not stationary) charges interact with magnetic fields."),
            
            
            # Lesson : The Magnetic Field
            ("The unit for measuring magnetic field strength is:", 
            ["Ampere", "Volt", "Tesla"], 
            2,
            "Magnetic field strength is measured in tesla (T)."),

            ("What law describes the relationship between current and magnetic field in a loop?", 
            ["Ohm's Law", "Ampere's Law", "Faraday's Law"], 
            1,
            "Ampere's Law relates loop current to magnetic field."),

            ("The right-hand rule helps determine:", 
            ["Magnetic field direction", "Strength of current", "Voltage across a wire"], 
            0,
            "Thumb: current direction; fingers: curl in magnetic field direction."),

            ("Magnetic fields around a straight wire form:", 
            ["Rectangles", "Concentric circles", "Parallel lines"], 
            1,
            "Field lines form concentric circles around a wire."),

            ("What happens if two parallel wires carry current in the same direction?", 
            ["Wires repel", "Wires attract", "No force"], 
            1,
            "Attraction occurs; opposite current directions cause repulsion."),

            ("The magnetic field along the axis of a current loop depends on:", 
            ["Area only", "Current, turns, radius", "Temperature"], 
            1,
            "Depends on current, number of turns, and loop radius."),

            ("Which law helps compute the field produced by a moving point charge?", 
            ["Biot-Savart Law", "Newton's Law", "Coulomb's Law"], 
            0,
            "Biot-Savart Law computes field by moving charges."),

            ("Moving electrons in atoms produce strong magnetic fields that affect:", 
            ["Other atoms", "The nucleus", "Gravity"], 
            1,
            "Orbiting electrons produce strong fields at the nucleus."),
            
            
            # Lesson : Capacitors in a Circuit
            ("A capacitor stores:", 
            ["Electric charge and energy", "Magnetic flux", "Heat"], 
            0,
            "Capacitors store electric charge and energy on their plates."),

            ("What is the formula for total capacitance in series?", 
            ["C_total = C1 + C2 + ...", "1/C_total = 1/C1 + 1/C2 + ...", "C_total = C1 × C2"], 
            1,
            "Add reciprocals for series: 1/C_total = 1/C1 + 1/C2 + ..." ),

            ("What is constant across all capacitors in a parallel circuit?", 
            ["Charge", "Current", "Voltage"], 
            2,
            "In parallel, voltage is the same across each capacitor."),

            ("In a series connection, what is true about the charge on each capacitor?", 
            ["Varies for each", "Is the same on every capacitor", "Depends on voltage"], 
            1,
            "Charge (Q) is the same on all capacitors in series." ),

            ("Adding more capacitors in parallel will:", 
            ["Increase total capacitance", "Decrease total capacitance", "Not affect capacitance"], 
            0,
            "Parallel combination increases total capacitance."),

            ("The capacitance of a parallel-plate capacitor depends on:", 
            ["Plate area and separation", "Shape only", "Voltage only"], 
            0,
            "Capacitance is proportional to plate area and inversely to distance between plates."),

            ("How can you increase the capacitance of a cylindrical capacitor?", 
            ["Make it shorter", "Make it longer or fatter", "Use less dielectric"], 
            1,
            "Longer length and more/larger dielectric increases capacitance of cylindrical capacitor."),

            ("A spherical capacitor's capacitance increases if you:", 
            ["Reduce the radius", "Use less dielectric", "Increase the radius and dielectric"], 
            2,
            "Greater radius and more dielectric boost spherical capacitor's capacitance."),
            
            
            # Lesson : Capacitance
            ("What does capacitance measure?", 
            ["Speed of current", "Ability to store charge", "Magnetic strength"], 
            1,
            "Capacitance measures a component’s ability to temporarily store electric charge."),

            ("Which of these makes capacitance larger?", 
            ["Smaller plate area", "Closer plate separation", "Worse dielectric"], 
            1,
            "Smaller distance between plates increases capacitance."),

            ("What's the formula for a parallel-plate capacitor's capacitance?", 
            ["C = ε(A/d)", "C = V/I", "C = Fv"], 
            0,
            "Capacitance C = ε(A/d): ε is permittivity, A area, d separation."),

            ("Why must the dielectric be an insulator?", 
            ["Allow current", "Prevent charge storage", "Allow storage and block continuous flow"], 
            2,
            "Insulating dielectric lets charges be stored—prevents current flow across plates."),

            ("Which factor does NOT increase capacitance?", 
            ["Larger plate area", "Worse dielectric", "Closer plate distance"], 
            1,
            "Worse (less insulating) dielectrics reduce capacitance."),

            ("Capacitance is measured in:", 
            ["Ohms", "Farads", "Joules"], 
            1,
            "The SI unit for capacitance is the farad (F)."),

            ("When a dielectric is improved, what happens to stored energy?", 
            ["Decreases", "Increases", "No effect"], 
            1,
            "Better dielectric allows more charge to be stored, increasing stored energy."),

            ("The voltage across a capacitor is most affected by:", 
            ["Charge and capacitance", "Plate color", "Magnetic field"], 
            0,
            "Voltage = Q/C; charge and capacitance directly determine voltage on a capacitor."),
            
            
            # Lesson : Magnetic Induction
            ("Electromagnetic induction produces:", 
            ["Heat", "Electromotive force (voltage)", "Sound"], 
            1,
            "Induction creates emf (voltage) and usually current in a circuit."),

            ("Faraday's Law states emf is induced when:", 
            ["A conductor moves in a magnetic field", "Current flows", "Temperature changes"], 
            0,
            "Relative motion or changing magnetic field induces emf."),

            ("Magnetic flux is measured in:", 
            ["Ampere", "Tesla", "Weber"], 
            2,
            "The unit for magnetic flux is weber (Wb)."),

            ("What is the formula for induced emf?", 
            ["emf = N(ΔΦ/Δt)", "emf = I/R", "emf = B × l × v"], 
            0,
            "emf = –N(ΔΦ/Δt); N is coil loops, Φ is flux change, t is time."),

            ("Increasing the number of loops in a coil will:", 
            ["Decrease emf", "Not affect emf", "Increase emf"], 
            2,
            "More loops increases the induced emf."),

            ("Which material type strongly increases magnetic field inside a solenoid?", 
            ["Diamagnetic", "Paramagnetic", "Ferromagnetic"], 
            2,
            "Ferromagnetic materials (iron, nickel) greatly boost field inside coils."),

            ("A moving magnet induces current because:", 
            ["It heats the wire", "It creates a changing magnetic flux", "It transfers charge directly"], 
            1,
            "Changing flux (motion, magnet strength, area change) creates emf."),

            ("Induced emf is greatest when:", 
            ["Magnet moves slowly", "Number of coil loops is small", "Magnet moves rapidly or number of loops is large"], 
            2,
            "Fast motion or many coil loops produces higher induced emf."),
            
            
            # Lesson : Image Formation in Lenses
            ("A converging lens is thicker at:", 
            ["The edges", "The center", "All places equally"], 
            1,
            "Converging lenses are thicker in the center than at the rims."),

            ("Which type of image is produced by a diverging lens?", 
            ["Real and inverted", "Virtual and upright", "Larger than the object"], 
            1,
            "Diverging lenses always produce virtual, upright, and smaller images."),

            ("The principal axis of a lens:", 
            ["Runs across the lens equator", "Passes through the center and the focal points", "Is only on one side"], 
            1,
            "Principal axis runs through the lens center and both focal points."),

            ("If the object is between F and the lens in a converging lens, the image will be:", 
            ["Real and inverted", "Virtual and upright", "No image formed"], 
            1,
            "Inside F, converging lens forms a virtual, upright, and larger image."),

            ("Focal length of a lens is:", 
            ["Distance from lens to object", "Distance from lens to principal axis", "Distance from lens center to focal point"], 
            2,
            "Focal length = center to focal point distance."),

            ("Which ray passes straight through the center of the lens in a ray diagram?", 
            ["Ray 1", "Ray 2", "Ray 3"], 
            1,
            "Ray 2 passes through the center and does not bend."),

            ("When the object is outside 2F in front of a converging lens, the image is located:", 
            ["Between F and 2F", "Beyond 2F", "At the principal axis"], 
            0,
            "Outside 2F, image appears between F and 2F, smaller and real."),

            ("Which is an application of lens image formation?", 
            ["Periscopes", "Eyeglasses and cameras", "Levers"], 
            1,
            "Glasses and cameras use lens image principles to focus light."),
            
            
            # Lesson : Snell's Law of Refraction
            ("Refraction is:", 
            ["Bending of light when entering new medium", "Light absorption", "Reflection from a surface"], 
            0,
            "Refraction: light bends at a boundary due to speed change."),

            ("Snell's law formula is:", 
            ["n₁sinθ₁ = n₂sinθ₂", "n₁/n₂ = sinθ₁/sinθ₂", "n₁sinθ₂ = n₂sinθ₁"], 
            0,
            "Snell's law relates angle and index: n₁sinθ₁ = n₂sinθ₂."),

            ("If n₁>n₂, and angle of incidence > critical angle, what happens?", 
            ["Refraction", "Total internal reflection", "Dispersion"], 
            1,
            "Light totally reflects at the boundary (total internal reflection)."),

            ("The critical angle formula (from n₁ to n₂, n₁>n₂):", 
            ["sinθ_c = n₂/n₁", "sinθ_c = n₁/n₂", "sinθ_c = θ₁/θ₂"], 
            0,
            "For critical angle: sin(θ_c) = n₂/n₁."),

            ("Dispersion happens because:", 
            ["Different colors refract by the same amount", "Different colors refract by different amounts", "Prisms block light"], 
            1,
            "Each color bends differently, separating into a spectrum."),

            ("Newton's prism experiment showed:", 
            ["White light is pure", "White light splits into different colors", "Only blue and red are present"], 
            1,
            "Prism shows white light splits—rainbow due to dispersion."),

            ("Absolute index of refraction of a medium is n = c/v. If c = 3.0×10⁸ m/s, v = 2.0×10⁸ m/s, then n = ?", 
            ["1.5", "0.67", "2.0"], 
            0,
            "n = 3.0×10⁸ / 2.0×10⁸ = 1.5."),

            ("Air has refractive index ~1.00; water 1.33. Which bends light rays more?", 
            ["Air", "Water", "Both same"], 
            1,
            "Higher index (water) bends rays more than air."),
            
            
            # Lesson : Common Properties of Light
            ("Light is best described as:", 
            ["A mechanical wave", "A transverse electromagnetic wave", "A longitudinal wave"], 
            1,
            "Light is a transverse electromagnetic wave."),

            ("Which property is NOT true of all waves?", 
            ["Carry energy", "Carry matter", "Have wavelength and frequency"], 
            1,
            "Waves transfer energy, not matter."),

            ("The speed of light in vacuum is:", 
            ["3.0 × 10⁸ m/s", "1.0 × 10⁶ m/s", "2.998 m/s"], 
            0,
            "Speed of light in vacuum is about 3.0 × 10⁸ m/s."),

            ("What is the formula for index of refraction?", 
            ["n = c/v", "n = v/c", "n = fλ"], 
            0,
            "n = c/v; c is light speed in vacuum, v in medium."),

            ("When light bounces from a surface, that is called:", 
            ["Refraction", "Reflection", "Diffusion"], 
            1,
            "Bouncing off a surface is reflection."),

            ("Law of reflection states:", 
            ["Angle in = angle out", "Angles are random", "Ray bends toward normal"], 
            0,
            "Angle of incidence = angle of reflection."),

            ("Regular reflection is found when light hits:", 
            ["Rough surface", "Smooth surface", "Absorptive material"], 
            1,
            "Smooth surfaces yield regular reflection."),

            ("When light bends entering a new medium, the effect is called:", 
            ["Reflection", "Refraction", "Absorption"], 
            1,
            "Bending when changing media is refraction."),

            ("Which experiment linked EM waves and light?", 
            ["Newton’s prism", "Hertz’s spark", "Faraday/Maxwell’s experiments"], 
            2,
            "Maxwell’s equations and experiments by Hertz and Faraday demonstrated light is an EM wave."),
            
            
            # Lesson : Behavior of Light in Optical Devices
            ("Plane mirrors always produce images that are:", 
            ["Real and enlarged", "Virtual and upright", "Inverted and real"], 
            1,
            "Plane mirrors always make virtual, upright images same size as object."),

            ("The focal length of a spherical mirror is the distance:", 
            ["From mirror to object", "From mirror to focus", "From focus to principal axis"], 
            1,
            "Focal length is distance from mirror to focus along principal axis."),

            ("Which device forms images using refraction?", 
            ["Mirror", "Lens", "Both"], 
            1,
            "Lenses use refraction; mirrors use reflection."),

            ("In a concave mirror, an object outside C forms an image:", 
            ["Real, inverted, reduced", "Virtual, upright, same size", "Virtual, upright, enlarged"], 
            0,
            "Object outside C on concave mirror makes real, inverted, reduced image."),

            ("Convex mirrors always produce images that are:", 
            ["Virtual and upright", "Real and inverted", "Real and upright"], 
            0,
            "Images in convex mirrors are always virtual and upright."),

            ("Paraxial approximation means:", 
            ["Using only rays far from the axis", "Considering only rays close to the principal axis", "Ignoring all rays"], 
            1,
            "Paraxial rays are close to axis, ensuring accurate image formation."),

            ("The ray that enters parallel to the principal axis:", 
            ["Reflects/refracts through the center", "Reflects/refracts through the focal point", "Remains parallel"], 
            1,
            "Parallel rays go through (or appear to come from) the focal point after reflection/refraction."),

            ("Which acronym helps describe images formed (location, orientation, size, type)?", 
            ["POST", "LOST", "FOCI"], 
            1,
            "LOST: Location, Orientation, Size, Type describes images in ray diagrams."),
            
            
            # Lesson : Mirror Equation
            ("Mirror equation relates object, image, and focal length as:", 
            ["1/f = 1/p + 1/q", "f = p + q", "1/f = p – q"], 
            0,
            "Spherical mirrors: 1/f = 1/p + 1/q for object/image distance and focal length."),

            ("What is the magnification formula for mirrors?", 
            ["m = –q/p", "m = q/p", "m = p/q"], 
            0,
            "m = –q/p gives both image size and orientation sign."),

            ("If magnification is negative, the image is:", 
            ["Virtual and upright", "Real and inverted", "None"], 
            1,
            "Negative magnification: real, inverted image."),

            ("What is always true for a plane mirror image?", 
            ["Real and enlarged", "Virtual, upright, same size", "Reduced and inverted"], 
            1,
            "Plane mirrors always make virtual, upright, same-sized images."),

            ("How does image type differ between concave and convex mirrors?", 
            ["Concave can form real; convex always virtual", "Convex can form real", "Both same"], 
            0,
            "Concave can form real or virtual; convex only virtual, upright, reduced."),

            ("For a convex mirror, what sign is used for focal length?", 
            ["Positive", "Negative", "Zero"], 
            1,
            "Focal length is negative for convex mirrors."),

            ("If object is at F (focus) of concave mirror, image will be:", 
            ["At center of curvature", "At infinity, no image", "Inverted and real"], 
            1,
            "Object at F: rays are parallel, produce no real image (image at infinity)."),

            ("To get an image one-fifth original size, erect, what type of mirror?", 
            ["Concave", "Convex", "Plane"], 
            1,
            "Convex mirrors always reduce and maintain upright virtual images."),
        ]

    def get_question(self, qid=None):
        if qid is None:
            qid = random.randrange(len(self.questions))
        q = self.questions[qid]
        return {'id': qid, 'prompt': q[0], 'choices': q[1], 'answer': q[2], 'explanation': q[3]}


class LessonPage:
    def __init__(self, title, lines):
        self.title = title
        self.lines = lines


# ------------------------
# Power-ups & Penalties
# ------------------------
class PowerUp:
    def __init__(self, name, duration=None):
        self.name = name
        self.duration = duration

    def apply(self, game):
        pass

    def remove(self, game):
        pass


class WidenPaddle(PowerUp):
    def __init__(self, amount=60):
        super().__init__('WidenPaddle', duration=None)
        self.amount = amount

    def apply(self, game):
        game.paddle.widen(self.amount)

    def remove(self, game):
        pass


class SlowBall(PowerUp):
    def __init__(self, factor=0.7, duration=10):
        super().__init__('SlowBall', duration)
        self.factor = factor

    def apply(self, game):
        game.ball.multiply_speed(self.factor)

    def remove(self, game):
        game.ball.multiply_speed(1.0 / self.factor)

class MultiBallPowerUp(PowerUp):
    def __init__(self, duration=10):
        super().__init__("Multi-Ball", duration)

    def apply(self, game):
        original_ball = game.ball
        if not hasattr(game, 'balls') or len(game.balls) <= 1:
            game.balls = [original_ball]
            for _ in range(2):
                new_ball = Ball(original_ball.pos.x, original_ball.pos.y,
                                original_ball.radius, original_ball.speed)
                angle = random.uniform(-3*math.pi/4, -math.pi/4)
                new_ball.vel = Vec2(math.cos(angle)*new_ball.speed, math.sin(angle)*new_ball.speed)
                game.balls.append(new_ball)

    def remove(self, game):
        if hasattr(game, 'balls') and len(game.balls) > 1:
            game.ball = game.balls[0]
            game.balls = [game.ball]

class ShieldPowerUp(PowerUp):
    def __init__(self, duration=6):
        super().__init__("Shield", duration)

    def apply(self, game):
        game.shield_active = True

    def remove(self, game):
        game.shield_active = False

class ScoreMultiplierPowerUp(PowerUp):
    def __init__(self, multiplier=2, duration=8):
        super().__init__("Score Multiplier", duration)
        self.multiplier = multiplier

    def apply(self, game):
        game.score_multiplier = self.multiplier

    def remove(self, game):
        game.score_multiplier = 1

class FreezeQuestionBlocksPowerUp(PowerUp):
    def __init__(self, duration=7):
        super().__init__("Freeze Question Blocks", duration)

    def apply(self, game):
        for block in game.blocks:
            if isinstance(block, SpecialBlock):
                block.frozen = True

    def remove(self, game):
        for block in game.blocks:
            if isinstance(block, SpecialBlock):
                block.frozen = False
                
class ExtraLifePowerUp(PowerUp):
    def __init__(self):
        super().__init__("Extra Life", duration=None)
    def apply(self, game):
        game.lives += 1
    def remove(self, game):
        pass
                
powerup_classes = [
        WidenPaddle,
        SlowBall,
        MultiBallPowerUp,
        ShieldPowerUp,
        ScoreMultiplierPowerUp,
        FreezeQuestionBlocksPowerUp,
        ExtraLifePowerUp,
]

# ------------------------
# UI helpers
# ------------------------
class Button:
    def __init__(self, rect, text, callback):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback

    def draw(self, surf, font):
        pygame.draw.rect(surf, (60, 60, 70), self.rect, border_radius=8)
        txt = font.render(self.text, True, TEXT_COLOR)
        surf.blit(txt, txt.get_rect(center=self.rect.center))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.callback()


# ------------------------
# The Game class
# ------------------------
class PhysiBreakGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('PhysiBreak')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(FONT_NAME, 20)
        self.large_font = pygame.font.Font(FONT_NAME, 36)
        
        self.create_difficulty_menu()
        
        self.countdown_active = False
        self.countdown_time_left = 0 # In seconds (e.g., 3 for a 3-second countdown)
        self.feedback_message = ""
        
        pygame.mixer.init()
        self.sfx_start_game = pygame.mixer.Sound("sfx/start_game.wav")
        self.sfx_hit_paddle = pygame.mixer.Sound("sfx/hit_paddle.wav")
        self.sfx_hit_block = pygame.mixer.Sound("sfx/hit_block.wav")
        self.sfx_powerup_spawn = pygame.mixer.Sound("sfx/powerup_spawn.wav")
        self.sfx_powerup_pick = pygame.mixer.Sound("sfx/powerup_pick.wav")
        self.sfx_correct = pygame.mixer.Sound("sfx/correct.wav")
        self.sfx_wrong = pygame.mixer.Sound("sfx/wrong.wav")
        self.sfx_lose_life = pygame.mixer.Sound("sfx/lose_life.wav")
        self.sfx_game_over = pygame.mixer.Sound("sfx/game_over.wav")
        for snd in [
            self.sfx_start_game,
            self.sfx_hit_paddle,
            self.sfx_hit_block,
            self.sfx_powerup_spawn,
            self.sfx_powerup_pick,
            self.sfx_correct,
            self.sfx_wrong,
            self.sfx_lose_life,
            self.sfx_game_over,
            ]:
            snd.set_volume(0.4)

        # Question and lesson resources MUST be created before reset_game_state
        self.qman = QuestionManager()
        self.lessons = [
            LessonPage('Units, Quantities, & Measurement', [
                "• Measurement assigns a numerical value and a unit to physical properties.",
                "• A physical quantity is anything that can be measured, like length, mass, or time.",
                "• Fundamental quantities: length (meter), mass (kilogram), time (second), temperature (kelvin), etc.",
                "• Derived quantities are made by combining fundamental ones, e.g., speed = distance/time.",
                "• Physical quantities have two components: a value and a unit (e.g., 5 meters).",
                "• Systems of measurement: English (inch, pound, gallon), Metric (meter, gram, liter), SI (international standard).",
                "• SI Units are universal in science, and easier to convert than English units.",
            ]),
            LessonPage('Unit Conversion', [
                "• Unit conversion is the process of changing the units of a measured quantity to another compatible unit.",
                "• To convert from a larger unit to a smaller unit, multiply (e.g., kilometers to meters: 1 km = 1000 m).",
                "• To convert from a smaller unit to a larger unit, divide (e.g., millimeters to centimeters: 20 mm ÷ 10 = 2 cm).",
                "• Common conversions: 1 foot = 12 inches; 1 inch = 2.54 centimeters; 1 kilogram = 2.2046 pounds.",
                "• Conversion between metric and English units requires using conversion factors.",
                "• Always use conversion factors for consistent and accurate conversions in calculations.",
            ]),
            LessonPage('Significant Figures', [
                "• Significant figures (sig figs) are the digits in a number that carry meaningful information.",
                "• They indicate the precision of a measurement or calculation.",
                "• Rules: 1) All non-zero digits are significant (e.g., 123 has 3 sig figs).",
                "• 2) Zeros between non-zero digits are significant (e.g., 1005 has 4 sig figs).",
                "• 3) Leading zeros are NOT significant (e.g., 0.0025 has 2 sig figs).",
                "• 4) Trailing zeros in a decimal are significant (e.g., 2.500 has 4 sig figs).",
                "• In calculations: for multiplication/division, use the fewest sig figs from any factor.",
                "• For addition/subtraction, round to the least precise decimal place.",
            ]),
            LessonPage('Scientific Notation', [
                "• Scientific notation expresses numbers as N × 10^x, for example: 4.67 × 10^9.",
                "• It is useful for very large or very small numbers (e.g., 200,000,000,000 stars, 0.000000000000000000000000006645 kg).",
                "• The coefficient (N) is between 1 and 10, and the exponent (x) tells how many times to multiply or divide by 10.",
                "• To convert a standard number to scientific notation, move the decimal until one non-zero digit remains left; count places to get the exponent.",
                "• Large numbers (decimal moved left) have positive exponents; small numbers (decimal moved right) have negative exponents.",
                "• To multiply in scientific notation: multiply the coefficients, add the exponents.",
                "• To divide: divide coefficients, subtract exponents.",
                "• For addition or subtraction: make exponents match, then add/subtract coefficients.",
            ]),
            LessonPage('Accuracy and Precision', [
                "• Accuracy: how close a measurement is to the true or accepted value.",
                "• Precision: how close multiple measurements are to each other (repeatability/consistency).",
                "•A measurement can be precise but not accurate (consistently wrong) or accurate but not precise (scattered around true value).",
                "• Measurement errors: Systematic errors are consistent biases (e.g., miscalibrated instrument).",
                "• Random errors vary unpredictably (e.g., reading angle, air currents, posture changes).",
                "• To minimize systematic error: calibrate equipment, use controls, compare to standards.",
                "• To handle random error: take multiple measurements and calculate the average.",
                "• Uncertainty in measurements can be expressed using standard deviation and standard error.",
            ]),
            LessonPage('Percent Error', [
                "• Percent error expresses the difference between a measured value and the true/accepted value as a percentage.",
                "• Formula: Percent Error = |(Experimental - Theoretical) / Theoretical| × 100%",
                "• It helps gauge how close a measured value is to the true value.",
                "• Steps: 1) Find the error (experimental - theoretical); 2) Divide by theoretical value; 3) Multiply by 100.",
                "• Percent error is usually expressed as a positive number (using absolute value).",
                "• Sometimes the sign is kept to show if measurements are consistently above or below the true value.",
                "• A small percent error indicates high accuracy; a large percent error shows poor accuracy.",
                "• Always express percent error with the % symbol.",
            ]),
            LessonPage('Scalars and Vectors', [
                "• Scalar quantities have only magnitude (size): mass, temperature, speed, distance, energy.",
                "• Vector quantities have both magnitude and direction: displacement, velocity, force, acceleration.",
                "• Vectors are represented by arrows: length = magnitude, direction = arrow head points the way.",
                "• Vector addition methods: Graphical (parallelogram, polygon) and Analytical (using components).",
                "• Parallelogram method (tail-to-tail): useful for adding two vectors.",
                "• Polygon method (head-to-tail): useful for adding multiple vectors in sequence.",
                "• Analytical method: break vectors into x, y components using trigonometry (SOH-CAH-TOA).",
                "• Resultant vector: the single vector that has the same effect as all the original vectors combined.",
            ]),
            LessonPage('Introduction to Kinematics', [
                "• Kinematics studies the motion of objects without reference to the causes (forces).",
                "• Distance is a scalar (total length of path taken); displacement is a vector (straight-line change in position).",
                "• Speed is a scalar: how fast an object is moving. Velocity is a vector: speed with direction.",
                "• Acceleration is the rate of change of velocity; it's a vector and can be positive or negative.",
                "• Time is a fundamental quantity, measured as the ongoing sequence of events.",
                "• Motion can be described with graphs (e.g., position vs. time, velocity vs. time). Slope on a d–t graph = velocity; on a v–t graph = acceleration.",
                "• Equations of uniformly accelerated motion (UAM) link displacement, velocity, acceleration, and time.",
                "• Problem-solving: identify known/unknown variables, pick the right equation, solve, and check units/reasonableness.",
            ]),
            LessonPage('Free Fall', [
                "• Free fall describes the motion of objects under the influence of gravity alone, neglecting air resistance.",
                "• All objects in free fall near Earth's surface experience the same acceleration, g ≈ 9.8 m/s², regardless of mass.",
                "• When dropped, an object starts from rest (initial velocity vi = 0) and gains speed while falling.",
                "• Equations of motion for free fall: vf = vi + gt ; d = vit + (1/2)gt² ; vf² = vi² + 2gd",
                "• Terminal velocity is reached when air resistance balances gravity, so acceleration stops and the object falls at constant speed.",
                "• Downward direction is taken as positive in free fall problems; upward as negative.",
                "• Sample calculation: To find time, use d = (1/2)gt²; To find final velocity, use vf = gt (if starting from rest).",
                "• Real-life examples: a ball dropped, cliff diving, falling coins, jumping animals like the tarsier.",
            ]),
            LessonPage('Motion in Two Dimensions', [
                "• Motion in two dimensions requires describing position, velocity, and acceleration as vectors (x and y components).",
                "• Projectile motion is a classic example: objects launched into the air follow a curved trajectory.",
                "• Horizontal (x) motion: constant velocity; Vertical (y) motion: constant acceleration due to gravity.",
                "• The two motions are independent; horizontal velocity does NOT affect vertical falling.",
                "• Trajectory is determined by initial velocity and angle, gravity, and starting height.",
                "• Equations for projectile motion: horizontal distance x = vx * t ; vertical displacement y = vy * t - (1/2)gt².",
                "• For angled launches: resolve initial velocity into horizontal (vx = v * cos θ) and vertical (vy = v * sin θ) components.",
                "• Find time of flight, maximum height, and range using kinematic equations; use trigonometry for vector components.",
            ]),
            LessonPage('Uniform Circular Motion', [
                "• Uniform circular motion describes objects moving in a circle at constant speed, with their direction continuously changing.",
                "• Velocity in circular motion is always tangent to the circle; speed stays constant but direction changes.",
                "• Acceleration in circular motion (centripetal acceleration) is directed toward the center of the circle; ac = v²/r.",
                "• Period (T) is the time to complete one revolution. Frequency (f) is the number of revolutions per second.",
                "• Tangential speed = circumference/time = 2πr/T ; radial (centripetal) acceleration = v²/r.",
                "• Centripetal force: the net force that keeps an object following a circular path, always pulling toward the center.",
                "• Centripetal force examples: friction for cars on a curve, gravity for planets in orbit, tension for a whirled ball.",
                "• No real outward (centrifugal) force acts on the object; 'centrifugal force' is a misconception—it's an effect of inertia.",
            ]),
            LessonPage('Newton\'s Laws of Motion', [
                "• Newton's First Law (Inertia): Objects at rest stay at rest, and objects in motion continue in straight lines at constant speed unless acted on by a net external force.",
                "• Newton's Second Law: The acceleration of an object is directly proportional to the net force acting on it and inversely proportional to its mass; mathematically, F = ma.",
                "• Newton's Third Law: For every action, there is an equal and opposite reaction; forces always come in pairs.",
                "• Two types of forces: Contact (e.g., friction, tension, normal) and Non-contact (e.g., gravity, magnetic, electrostatic).",
                "• A free-body diagram shows all the forces acting on an object as arrows; the length and direction represent the magnitude and direction.",
                "• In dynamics, a net force causes change in the motion of an object; zero net force means equilibrium.",
                "• Normal force acts perpendicular to a surface; friction acts parallel and opposes motion; weight is always downward due to gravity.",
                "• Apply Newton's Laws to everyday questions, like why passengers lurch forward when a bus stops (inertia), or who wins tug of war (net force).",
            ]),
            LessonPage('Work, Power, and Mechanical Energy', [
                "• Energy is the ability to do work. There are two main mechanical energies: kinetic (motion) and potential (position).",
                "• Work is done when a force causes displacement. W = F × d × cos(θ), where θ is the angle between force and displacement.",
                "• The SI unit of work is the joule (J). If force and displacement are parallel, W = F × d.",
                "• Potential Energy (PE) is stored due to position: PE = mgh, where m is mass, g is gravity, h is height.",
                "• Kinetic Energy (KE) is energy of motion: KE = (1/2)mv², where m is mass and v is speed.",
                "• Power is the rate of doing work: P = Work/time, measured in watts (W).",
                "• Mechanical energy is the total energy due to position and motion, ME = KE + PE.",
                "• Work done against gravity increases potential energy; work done by gravity decreases it and increases kinetic energy.",
            ]),
            LessonPage('Electric Charges', [
                "• Electric charge is a property of matter that causes it to experience a force when near other charged matter.",
                "• Types: Positive (proton), Negative (electron), Neutral (equal protons/electrons; neutron).",
                "• Like charges repel, unlike charges attract (Coulomb’s Law describes the force magnitude).",
                "• Materials can be charged by rubbing (friction), conduction (contact), or induction (no contact, using ground wire).",
                "• Conductors allow charges to move freely; insulators do not.",
                "• The triboelectric series predicts which material becomes positive or negative when rubbed with another.",
                "• An ion forms if an atom gains (anion, negative) or loses (cation, positive) electrons.",
                "• Net charge of an object = sum of all its positive and negative charges.",
                "• In conduction, touching transfers charge; in induction, the opposite charge is induced by a nearby charged object.",
            ]),
            LessonPage('Electrostatic Force', [
                "• Electrostatic force is the force of attraction or repulsion between electric charges; it acts at a distance and is described by Coulomb's Law.",
                "• Coulomb's Law: F = k * |Q1 * Q2| / r² ; where Q1 and Q2 are charges, r is distance, k ≈ 8.99 × 10⁹ N·m²/C².",
                "• Like charges repel; unlike charges attract. The force is stronger with larger charges and weaker with greater distance.",
                "• Charge is measured in coulombs (C), microcoulombs (μC), or nanocoulombs (nC).",
                "• Superposition principle: total force on a charge is the sum of separate forces from all other charges present.",
                "• Electric field (E): region around a charge where electrostatic force can be felt; E = F/q, measured in newtons per coulomb (N/C).",
                "• Dipoles: neutral bodies with separated positive and negative sides, leading to electrical behavior.",
                "• Polarization refers to the shifting of charges within molecules, resulting in temporary or permanent dipoles.",
                "• Examples and problems include calculating force or field for different charge arrangements—critical for understanding molecular interactions.",
            ]),
            LessonPage('Electric Field Lines', [
                "• Electric field lines graphically represent the direction and strength of electric fields.",
                "• Field lines start on positive charges and end on negative charges.",
                "• The density of field lines shows field strength: closer together means stronger field.",
                "• For a point charge, lines radiate outward (positive) or inward (negative). Around two charges, lines bend to show attraction or repulsion.",
                "• At the center of a dipole, field lines curve from positive to negative, never crossing.",
                "• Electric flux measures the total field passing through an area: Φ = E × A × cos(θ), where θ is the angle relative to surface normal.",
                "• Flux unit: volt-meter (V·m) or newton-meter squared per coulomb (N·m²/C).",
                "• Gauss’s Law: The total electric flux through a closed surface equals net charge inside, divided by the permittivity of free space.",
                "• Applications: visualizing fields from charged balls, plates, lines; predicting forces and behavior in atoms and circuits.",
            ]),
            LessonPage('Electric Circuits', [
                "• An electric circuit is a closed pathway that allows electric current to flow from a source to a load (like a bulb).",
                "• A functional circuit must be closed—with no gaps in the loop—or else current cannot flow (open circuit = no current).",
                "• Series circuit: has only one path for current; current is the same everywhere, total resistance is the sum of all resistors.",
                "• Parallel circuit: provides multiple paths for current; voltage is the same across all branches, but current divides among branches.",
                "• Schematic diagrams are simplified drawings of circuits using standard symbols (e.g., cell, resistor, ammeter, voltmeter).",
                "• In series circuits: V_total = V1 + V2 + ... ; R_total = R1 + R2 + ... ; I is constant.",
                "• In parallel circuits: voltage is the same across each branch; I_total = I1 + I2 + ... ; 1/R_total = 1/R1 + 1/R2 + ...",
                "• Ammeters measure current (connected in series); voltmeters measure voltage (connected in parallel).",
                "• Practice activities often involve drawing circuits and calculating current, voltage, and resistance in both types.",
            ]),
            LessonPage('Electric Potential', [
                "• Electric potential (V) is the amount of electric potential energy per unit charge; it represents the work needed to move a charge from one point to another.",
                "• V = W/q, where V is potential (volts), W is work (joules), and q is charge (coulombs).",
                "• The potential created by a point charge at distance r: V = kQ/r.",
                "• Equipotential lines are loops drawn around a charge; at any point in a loop, the potential is constant, and no work is required to move a charge along the line.",
                "• Equipotential lines are always perpendicular to electric field lines.",
                "• As electric field strength weakens with distance, electric potential increases, and vice versa.",
                "• Gravitational potential energy is similar: higher objects have more potential energy due to elevated position.",
                "• If moving from high to low potential, positive charges 'fall' toward lower potential; negative charges 'climb' toward higher potential.",
            ]),
            LessonPage('Usage of Electricity', [
                "• Electricity is essential in daily life, powering devices and providing light, heat, and energy for work.",
                "• Electric power (P) is calculated: P = V × I, where V is voltage and I is current; measured in watts (W), kilowatts (kW), megawatts (MW), gigawatts (GW).",
                "• A closed circuit enables energy delivery—current flows from source to device, transforming into useful forms (light, heat, work).",
                "• Power lost due to resistance is calculated using Ohm’s Law and can convert electric energy to heat: heat rate = I²R.",
                "• Choosing appliances with lower current needs helps save electricity and prevents power loss.",
                "• Examples: Calculating resistance or heat produced by appliances, understanding energy consumption for heaters, bulbs, flashlights.",
                "• Improper use of electricity is hazardous: electric shock affects the human body at different current levels (0.001 A: tingling, 0.01-0.19 A: muscle spasm, 0.2+ A: heart fibrillation, >0.2 A: heart stops).",
                "• Electrical safety is crucial; use protective devices and proper procedures to avoid accidents and injuries.",
            ]),
            LessonPage('Resistance and Resistivity', [
                "• Resistance is the property of a material or device that opposes or limits the flow of electric current; measured in ohms (Ω).",
                "• Resistivity is an intrinsic property of a material that determines how much material resists current; symbol: ρ (rho).",
                "• Resistance and current are inversely proportional: more resistance means less current can flow and vice versa.",
                "• Factors affecting resistance: (1) Material’s resistivity, (2) Length—longer wires offer more resistance, (3) Cross-sectional area—thicker wires offer less resistance, (4) Temperature—in most conductors, higher temperature increases resistance.",
                "• Resistance formula: R = ρ × (L/A); where L = length, A = area, and ρ = resistivity of the material.",
                "• Electrical conductivity is the opposite of resistivity; more conductive materials offer less resistance.",
                "• Fat/thick conductors allow more current due to low resistance; thin conductors have high resistance and pass less current.",
                "• Current flow is reduced by an increase in resistivity, increased length, reduced area, or high temperature.",
                "• Activity: Predict changes in resistance and current as you vary material properties: resistivity, length, area, and temperature.",
            ]),
            LessonPage('Electric Current', [
                "• Electric current is the continuous flow of electric charges (usually electrons) through a conductor.",
                "• Current flows due to electric potential energy, which pushes electrons from high to low potential.",
                "• Drift velocity: average speed electrons move through the conductor; higher drift velocity means higher current.",
                "• Current is directly proportional to the amount of charge passing a point per second.",
                "• Formula: I = Q/t, where I is current (amperes, A), Q is charge (coulombs, C), and t is time (seconds, s).",
                "• A steady current of 0.6 A flows through a wire: in one minute (60 s), 0.6 × 60 = 36 C of charge passes.",
                "• High current density and drift velocity occur when more electrons are present and repulsion between electrons is strong.",
                "• Electric current can be measured using an ammeter; unit is ampere (A).",
            ]),
            LessonPage('Voltage, Current, and Resistance', [
                "• Voltage (V), also called electromotive force (EMF) or potential difference (PD), is the energy provided to electric charges to make them flow through a conductor or circuit. Measured in volts (V).",
                "• EMF is the potential energy per unit charge provided by a source (like a battery); it's the 'push' causing charges to flow.",
                "• Without a voltage source, there is no push and no current in the circuit.",
                "• Current (I) is the rate of flow of electric charges through the circuit; measured in amperes (A).",
                "• Resistance (R) is the opposition to the flow of current; measured in ohms (Ω). High resistance means lower current.",
                "• Ohm’s Law: V = IR ; current is directly proportional to voltage and inversely proportional to resistance.",
                "• Devices like bulbs, heaters, and resistors use voltage to create current, and their resistance affects how much current flows.",
                "• Analogy: Electricity in a wire acts similarly to water in a pipe—voltage is water pressure, current is flow rate, resistance is pipe width.",
            ]),
            LessonPage('Magnetism', [
                "• Magnetism is the force exerted by magnets when they attract or repel other materials, due to the alignment of atoms (magnetic domains).",
                "• A magnet always has two poles: north and south. Like poles repel, unlike poles attract.",
                "• Cutting a magnet in half creates two smaller magnets, each with its own north and south poles.",
                "• Magnetic field: Region around a magnetic pole where force is felt; visualized by field lines.",
                "• Field lines emerge from the north pole and enter the south pole; dense lines mean a strong field.",
                "• Magnets can be demagnetized by hammering, heating, or AC exposure; remagnetized by strong magnetic fields.",
                "• Comparison: Both electric and magnetic interactions involve attraction and repulsion, but electric charges can exist alone while magnetic poles cannot.",
                "• Motion of electric charges (current) produces magnetism—demonstrated by Oersted when he saw compass deflection near a current.",
                "• Charged particles only interact with magnetic fields while moving; stationary charges do not experience magnetic force.",
            ]),
            LessonPage('The Magnetic Field', [
                "• A magnetic field is the region around a magnet or current-carrying wire where magnetic forces are felt; it is visualized by field lines and measured in tesla (T).",
                "• Ampere's Law: Current passing through a loop produces a net magnetic field in and around the loop; mathematically relates the current to the magnetic field produced.",
                "• Biot-Savart Law: Describes the magnetic field created by a moving point charge, a current element, or a straight conductor.",
                "• Magnetic field direction is determined by the right-hand rule: thumb points along current, fingers curl in the direction of field.",
                "• Magnetic fields around a straight current-carrying wire form concentric circles; field strength is proportional to current, inversely proportional to distance.",
                "• Two parallel current-carrying wires exert forces on each other: attraction if currents go the same way, repulsion if they go oppositely.",
                "• A current loop produces a magnetic field along its axis; direction is set by the right-hand rule, and strength depends on the current, number of turns, and radius.",
                "• Orbiting electrons produce strong magnetic fields at the nucleus—key to atomic structure.",
                "• Applications: electric motors, magnetic levitation, generators, and electromagnetic interactions in circuits.",
            ]),
            LessonPage('Capacitors in a Circuit', [
                "• A capacitor stores electric charge and energy; it consists of two conductors (plates) separated by a dielectric (insulator).",
                "• Total capacitance in series: 1/C_total = 1/C1 + 1/C2 + ...; series connection provides lower total capacitance than any individual capacitor.",
                "• Total capacitance in parallel: C_total = C1 + C2 + ...; parallel connection provides higher total capacitance.",
                "• In series: charge (Q) is constant, total voltage is the sum of individual voltages (V_total = V1 + V2 + ...).",
                "• In parallel: voltage (V) is constant, total charge is the sum of individual charges (Q_total = Q1 + Q2 + ...).",
                "• Shapes: common capacitors are parallel-plate, cylindrical, or spherical. Capacitance depends on geometry and dielectric properties.",
                "• For a parallel-plate capacitor, capacitance increases with plate area and decreases with distance between plates.",
                "• A cylindrical capacitor’s capacitance increases with its length and with a larger dielectric.",
                "• A spherical capacitor: larger radius and more dielectric both increase capacitance.",
                "• Capacitors are widely used for energy storage, filtering, and timing in electronic circuits.",
            ]),
            LessonPage('Capacitance', [
                "• Capacitance is a property of a capacitor that is its ability to store electric charge; measured in farads (F).",
                "• A capacitor consists of two conducting plates separated by an insulator (dielectric).",
                "• Capacitance depends on plate area (larger area, more capacitance), the distance between plates (closer plates, more capacitance), and the type of dielectric (better insulator, more capacitance).",
                "• Formula: C = ε(A/d), where ε is the permittivity of the dielectric, A is plate area, d is separation.",
                "• Increasing the area or using a better dielectric increases capacitance; increasing plate distance decreases it.",
                "• The dielectric blocks continuous current but allows the capacitor to store energy by holding charges on each plate until discharge.",
                "• Greater capacitance means the capacitor can store more energy, in the form of potential energy, for later discharge.",
                "• Real applications: smoothing power supply fluctuations, storing charge in electronic circuits, energy backup.",
            ]),
            LessonPage('Magnetic Induction', [
                "• Magnetic induction is the process by which a changing magnetic field induces an electromotive force (emf) and often a current in a conductor.",
                "• Electromagnetic induction (Faraday's Law): A voltage (emf) is produced whenever relative motion exists between a conductor and a magnetic field, or when the magnetic field within a loop of wire changes over time.",
                "• Magnetic flux (Φ): Measures the strength of the magnetic field passing through a given area; Φ = B × A × cos(θ), units: weber (Wb).",
                "• Faraday’s Law formula: emf = –N(ΔΦ/Δt), where N is the number of coil loops, ΔΦ is change in flux, Δt is change in time.",
                "• Factors increasing induced emf: more wire loops, faster change of flux (move magnet faster), stronger magnetic field.",
                "• Relative permeability: Different materials inside solenoids (diamagnetic, paramagnetic, ferromagnetic) change magnetic field strength.",
                "• Applications: Generators, motors, transformers, induction heating, wireless charging, and energy storage.",
                "• A closed surface in magnetic induction has zero net flux due to field lines entering and exiting.",
                "• Examples involve calculating flux, emf for solenoids/coils, and predicting effects of material, geometry, and movement.",
            ]),
            LessonPage('Image Formation in Lenses', [
                "• Lenses are optical devices made of clear material that refract (bend) light rays, focusing or dispersing them.",
                "• Converging lenses (thicker in the center) focus light to a point; diverging lenses (thinner in the center) spread light from a virtual point.",
                "• Focal length (f): distance from center of the lens to focal point; positive for converging, negative for diverging lenses.",
                "• There are two focal points (one each side); principal axis runs through the center of the lens and the focal points.",
                "• Real images are formed when refracted rays actually meet; virtual images are formed when rays appear to diverge from a point.",
                "• Ray diagrams: Key rays include (1) parallel to axis—through F; (2) through center—straight line; (3) through F—comes out parallel.",
                "• For a converging lens: image can be real/inverted (object outside F), or virtual/upright (object inside F).",
                "• For a diverging lens: image is always virtual, upright, and smaller than the object.",
                "• Applications: eyeglasses, microscopes, cameras, and telescopes all use lens image formation principles.",
            ]),
            LessonPage('Snell\'s Law of Refraction', [
                "• When light passes from one medium to another, its speed and direction change; this bending is called refraction.",
                "• Snell's Law describes refraction: n₁sinθ₁ = n₂sinθ₂, where n₁, n₂ are refractive indices and θ₁, θ₂ angles to the normal.",
                "• Absolute index of refraction: n = c/v (c = speed of light in vacuum, v = speed of light in medium). Higher n means slower light and more bending.",
                "• Critical angle: the incident angle in the denser medium where refracted angle reaches 90°, causes total internal reflection; calculated using sinθ_c = n₂/n₁ (for light from n₁ to n₂, n₁>n₂).",
                "• Total internal reflection: occurs if angle of incidence > critical angle, all light reflects back inside medium.",
                "• Dispersion: different colors of light refract differently, causing white light to spread into a spectrum (as in a prism).",
                "• Newton's prism experiment showed white light splits into rainbow colors due to variation in speed and refraction for each color.",
                "• Refractive indices for common materials: air (1.00), water (1.33), glass (≈1.5), diamond (2.42); higher index means greater bending.",
            ]),
            LessonPage('Common Properties of Light', [
                "• Light is an electromagnetic (EM) wave—a transverse wave that carries energy and can travel through space without any medium.",
                "• Waves have properties: wavelength (distance between crests or troughs), frequency (number of waves per second), and speed.",
                "• In a vacuum, all EM waves travel at the speed of light (c ≈ 3.0 × 10⁸ m/s). Speed in other media depends on permittivity and permeability—and is always slower than in vacuum.",
                "• Reflection: Light bounces when hitting a surface. Law of reflection: angle of incidence equals angle of reflection. Regular reflection occurs on smooth surfaces, diffused reflection on rough ones.",
                "• Refraction: Light bends as it passes between media with different refractive indices due to a change in speed. Index formula: n = c/v.",
                "• Light does not carry matter; it only transfers energy. EM waves: light, radio, X-rays, microwaves, gamma rays, etc.",
                "• Maxwell’s equations and Faraday’s and Hertz’s experiments showed that oscillating electric and magnetic fields produce EM waves, linking electricity, magnetism, and light.",
                "• Transverse waves (like light) move energy perpendicular to particle motion; longitudinal waves move energy parallel. Light’s color and energy depend on wavelength and frequency.",
            ]),
            LessonPage('Behavior of Light in Optical Devices', [
                "• Optical devices like mirrors and lenses form images by reflecting or refracting light rays.",
                "• Mirrors form images using the law of reflection; plane mirrors create virtual, upright images, while spherical mirrors (concave/convex) can create real or virtual images based on object location.",
                "• Lenses form images using refraction; converging lenses can focus to form real or virtual images, diverging lenses produce virtual images only.",
                "• The principal axis passes through the center, focal point, and (for mirrors) center of curvature; focal length (f) is the distance from the center to the focal point.",
                "• Paraxial approximation: only rays close to the principal axis are considered for accurate image location, size, and type predictions.",
                "• Ray diagrams: Use parallel rays (reflect/refract to/from F), rays through the center (pass straight), and rays through F (come out parallel).",
                "• LOST acronym: Location (where image forms), Orientation (upright/inverted), Size (reduced/enlarged/same), Type (real or virtual).",
                "• Concave mirrors outside C: real, inverted, reduced; between C and F: real, inverted, enlarged; inside F: virtual, upright, enlarged.",
                "• Convex mirrors: image always virtual, upright, reduced, on the opposite side of mirror.",
                "• Ray tracing helps, especially for lenses, to determine exactly how and where the eye will see the image formed by an object.",
            ]),
            LessonPage('Mirror Equation', [
                "• The mirror equation mathematically relates object distance, image distance, and focal length for spherical mirrors: 1/f = 1/p + 1/q, with p = object distance, q = image distance, f = focal length.",
                "• Magnification (m) describes size and orientation: m = –q/p ; if |m|>1 image is enlarged, if |m|<1 image is reduced, if m is negative image is inverted, if m is positive image is upright.",
                "• Sign convention: for concave mirrors, f and q are positive when object or image is in front; for convex mirrors, f is negative and images form behind (virtual, upright, reduced).",
                "• Ray diagramming helps estimate image location, but the mirror equation gives accurate values for image distance, size, and characteristics.",
                "• Plane mirrors always have virtual, upright images same size as the object (m = 1).",
                "• Concave mirror: object outside F – real, inverted, possibly reduced; object inside F – virtual, upright, enlarged.",
                "• Convex mirror: always virtual, upright, reduced image, image forms behind the mirror.",
                "• Practice problems involve finding q, m, image type, and orientation given p, f, and sometimes object height.",
            ]),
        ]

        # initialize game state after resources exist
        self.reset_game_state()

        # UI
        self.menu_buttons = []
        self.create_menu()

    def reset_game_state(self):
        paddle_width = getattr(self, 'paddle_width', PADDLE_WIDTH)
        self.paddle = Paddle(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40, width=paddle_width)
        ball_speed = getattr(self, 'ball_speed', BALL_SPEED)
        self.ball = Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80, speed=ball_speed)
        self.balls = [self.ball]
        self.score = 0
        self.lives = getattr(self, 'starting_lives', 3)
        self.level = 1
        self.blocks = []
        self.active_powerups = []  # list of tuples (powerup, remaining_time)
        self.shield_active = False
        self.score_multiplier = 1
        self.paused = False
        self.show_question = False
        self.current_question = None
        self.generate_level()

    def create_menu(self):
        cx = SCREEN_WIDTH // 2
        self.menu_buttons = [
            Button((cx - 120, 280, 240, 52), 'Start Game', self.go_to_difficulty_select),
            Button((cx - 120, 350, 240, 52), 'Lessons', lambda: self.open_lessons()),
            Button((cx - 120, 420, 240, 52), 'Quit', lambda: self.quit_game()),
        ]
        self.lesson_index = 0

    def create_difficulty_menu(self):
        cx = SCREEN_WIDTH // 2
        self.difficulty_buttons = [
            Button((cx - 120, 280, 240, 52), 'Easy', lambda: self.start_game_with_difficulty('easy')),
            Button((cx - 120, 350, 240, 52), 'Normal', lambda: self.start_game_with_difficulty('normal')),
            Button((cx - 120, 420, 240, 52), 'Hard', lambda: self.start_game_with_difficulty('hard')),
        ]
        
    def go_to_difficulty_select(self):
        self.state = 'difficulty_select'

        
    def start_game_with_difficulty(self, difficulty):
        self.difficulty = difficulty
        if difficulty == 'easy':
            self.ball_speed = 4.0
            self.lives = 5
            self.starting_lives = 5
            self.paddle_width = PADDLE_WIDTH + 40
        elif difficulty == 'normal':
            self.ball_speed = 5.5
            self.lives = 3
            self.starting_lives = 3
            self.paddle_width = PADDLE_WIDTH
        elif difficulty == 'hard':
            self.ball_speed = 7.0
            self.lives = 2
            self.starting_lives = 2
            self.paddle_width = PADDLE_WIDTH - 40
        self.reset_game_state()
        self.sfx_start_game.play()
        self.state = 'playing'

    def start_game(self):
        self.reset_game_state()
        self.sfx_start_game.play()
        self.state = 'playing'

    def open_lessons(self):
        self.state = 'lessons'
        self.lesson_index = 0

    def quit_game(self):
        pygame.quit()
        sys.exit()
        
    def create_game_over_menu(self):
        cx = SCREEN_WIDTH // 2
        self.game_over_buttons = [
            Button((cx - 120, 320, 240, 52), 'Retry', self.retry_game),
            Button((cx - 120, 400, 240, 52), 'Menu', self.return_to_menu),
        ]

    def retry_game(self):
        self.reset_game_state()
        self.sfx_start_game.play()
        self.state = 'playing'

    def return_to_menu(self):
        self.state = 'menu'


    def generate_level(self):
        # Make sure qman is available (safety guard)
        if not hasattr(self, 'qman'):
            self.qman = QuestionManager()

        self.blocks = []
        grid_width = BLOCK_COLS * (BLOCK_WIDTH + BLOCK_PADDING) - BLOCK_PADDING
        start_x = (SCREEN_WIDTH - grid_width) // 2
        rows = BLOCK_ROWS + self.level - 1
        cols = BLOCK_COLS + self.level - 1
        for r in range(rows):
            for c in range(cols):
                x = start_x + c * (BLOCK_WIDTH + BLOCK_PADDING)
                y = TOP_OFFSET + r * (BLOCK_HEIGHT + BLOCK_PADDING)
                question_chance = min(0.2 + 0.05 * (self.level - 1), 0.8)
                if random.random() < question_chance:
                    q = self.qman.get_question()
                    b = SpecialBlock(x, y, BLOCK_WIDTH, BLOCK_HEIGHT, q['id'])
                else:
                    b = Block(x, y, BLOCK_WIDTH, BLOCK_HEIGHT)
                self.blocks.append(b)

    def spawn_powerup(self, powerup):
        # Immediately apply and track to remove later if timed
        powerup.apply(self)
        self.sfx_powerup_spawn.play()
        if powerup.duration:
            self.active_powerups.append([powerup, powerup.duration])

    def apply_penalty(self, penalty):
        # penalty: function(game)
        penalty(self)

    # ------------------------
    # Collision helpers
    # ------------------------
    def handle_collisions(self):
        b = self.ball
        # Walls
        if b.pos.x - b.radius <= 0:
            b.pos.x = b.radius
            b.reflect_horizontal()
        if b.pos.x + b.radius >= SCREEN_WIDTH:
            b.pos.x = SCREEN_WIDTH - b.radius
            b.reflect_horizontal()
        if b.pos.y - b.radius <= 0:
            b.pos.y = b.radius
            b.reflect_vertical()

        # Paddle
        if self.paddle.rect.collidepoint(b.pos.x, b.pos.y + b.radius):
            # reflect with angle depending on where it hits the paddle
            rel = (b.pos.x - self.paddle.x) / (self.paddle.width / 2)  # -1 .. 1
            rel = max(-1.0, min(1.0, rel))
            max_bounce_angle = math.radians(75)
            angle = rel * max_bounce_angle
            speed = math.hypot(b.vel.x, b.vel.y)
            b.vel.x = math.sin(angle) * speed
            b.vel.y = -abs(math.cos(angle) * speed)
            # small nudge to avoid sticking
            b.pos.y = self.paddle.rect.y - b.radius - 1

        # Blocks
        for block in self.blocks:
            if not block.alive:
                continue
            if block.rect.collidepoint(b.pos.x, b.pos.y - b.radius) or block.rect.collidepoint(b.pos.x, b.pos.y + b.radius) or block.rect.collidepoint(b.pos.x - b.radius, b.pos.y) or block.rect.collidepoint(b.pos.x + b.radius, b.pos.y):
                # Basic collision: reverse y-velocity if hit from top/bottom, else reverse x
                overlap_x = (b.pos.x - max(block.rect.left, min(b.pos.x, block.rect.right)))
                overlap_y = (b.pos.y - max(block.rect.top, min(b.pos.y, block.rect.bottom)))
                if abs(overlap_x) > abs(overlap_y):
                    b.reflect_horizontal()
                else:
                    b.reflect_vertical()

                if isinstance(block, SpecialBlock):
                    # fetch the exact question for this block
                    self.current_question = self.qman.get_question(block.question_id)
                    self.show_question = True
                    # keep block alive until question answered
                else:
                    block.hit()
                    if not block.alive:
                        self.score += 10
                break

    # ------------------------
    # Question handling
    # ------------------------
    def draw_question(self):
        if not self.current_question:
            return []
        # modal background
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 10, 200))
        self.screen.blit(overlay, (0, 0))

        # question box
        box_w, box_h = 720, 360
        r = pygame.Rect((SCREEN_WIDTH - box_w)//2, (SCREEN_HEIGHT - box_h)//2, box_w, box_h)
        pygame.draw.rect(self.screen, (40, 40, 50), r, border_radius=10)
        pygame.draw.rect(self.screen, (100, 100, 110), r, width=2, border_radius=10)

        # text
        lines = [self.current_question['prompt']]
        y = r.y + 20
        wrapped = self.wrap_text(lines[0], box_w - 40, self.font)
        for ln in wrapped:
            txt = self.font.render(ln, True, TEXT_COLOR)
            self.screen.blit(txt, (r.x + 20, y))
            y += txt.get_height() + 6

        # choices
        choice_rects = []
        for i, choice in enumerate(self.current_question['choices']):
            cr = pygame.Rect(r.x + 20, y + i * 48, r.w - 40, 44)
            pygame.draw.rect(self.screen, (60, 60, 70), cr, border_radius=8)
            txt = self.font.render(f"{chr(65+i)}. {choice}", True, TEXT_COLOR)
            self.screen.blit(txt, (cr.x + 12, cr.y + 10))
            choice_rects.append(cr)

        return choice_rects

    def wrap_text(self, text, max_width, font):
        words = text.split(' ')
        lines = []
        cur = ''
        for w in words:
            test = cur + (' ' if cur else '') + w
            if font.size(test)[0] <= max_width:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def answer_question(self, choice_index):
        if not self.current_question:
            return
        
        correct = (choice_index == self.current_question['answer'])
        
        if correct:
            self.sfx_correct.play()
        else:
            self.sfx_wrong.play()
            
        if correct:
            self.feedback_message = self.current_question['explanation']
        else:
            self.feedback_message = ""
            
        if correct:
            # reward - choose a random power-up
            reward_class = random.choice(powerup_classes)
            self.spawn_powerup(reward_class())
            # find and remove any special block that matches this question
            self.sfx_powerup_pick.play()
            for block in self.blocks:
                if isinstance(block, SpecialBlock) and block.question_id == self.current_question['id']:
                    block.hit()  # will set alive False
        else:
            # penalty: speed up ball and shrink paddle
            self.ball.multiply_speed(1.25)
            self.paddle.shrink(14)
            # Also reveal explanation (simple feedback)
        
        self.current_question = None  # Display this in your draw function
        self.countdown_time_left = 1  # 3 seconds countdown
        self.countdown_active = True
        self.show_question = False

    # ------------------------
    # Main loop & states
    # ------------------------
    def run(self):
        self.state = 'menu'
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit_game()
            if self.state == 'menu':
                for btn in self.menu_buttons:
                    btn.handle_event(event)
            elif self.state == 'difficulty_select':
                for btn in self.difficulty_buttons:
                    btn.handle_event(event)
            elif self.state == 'game_over':
                for btn in self.game_over_buttons:
                    btn.handle_event(event)
            elif self.state == 'lessons':
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = 'menu'
                    elif event.key == pygame.K_LEFT:
                        self.lesson_index = max(0, self.lesson_index - 1)
                    elif event.key == pygame.K_RIGHT:
                        self.lesson_index = min(len(self.lessons) - 1, self.lesson_index + 1)
            elif self.state == 'playing':
                if self.show_question:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        # We need choice rects to test clicks but avoid drawing twice: compute rects
                        crs = self.draw_question()  # draw_question is idempotent here (safe)
                        for idx, cr in enumerate(crs):
                            if cr.collidepoint(event.pos):
                                self.answer_question(idx)
                    if event.type == pygame.KEYDOWN:
                        if pygame.K_a <= event.key <= pygame.K_d:
                            idx = event.key - pygame.K_a
                            if self.current_question and idx < len(self.current_question['choices']):
                                self.answer_question(idx)
                else:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.state = 'menu'
            # universal mouse control for paddle will be in update

    def update(self, dt):
        if self.countdown_active:
            self.countdown_time_left -= dt
            if self.countdown_time_left <= 0:
                self.countdown_active = False
                self.feedback_message = ""  # Hide feedback message
            return
        
        if self.state == 'playing':
            if not self.show_question:
                self.paddle.update(SCREEN_WIDTH)
                
                # Update all balls
                for ball in self.balls:
                    ball.update()

                # Handle collisions for all balls
                for ball in self.balls:
                    b = ball
                    # Walls
                    if b.pos.x - b.radius <= 0:
                        b.pos.x = b.radius
                        b.reflect_horizontal()
                    if b.pos.x + b.radius >= SCREEN_WIDTH:
                        b.pos.x = SCREEN_WIDTH - b.radius
                        b.reflect_horizontal()
                    if b.pos.y - b.radius <= 0:
                        b.pos.y = b.radius
                        b.reflect_vertical()

                    # Paddle
                    if self.paddle.rect.collidepoint(b.pos.x, b.pos.y + b.radius):
                        rel = (b.pos.x - self.paddle.x) / (self.paddle.width / 2)
                        rel = max(-1.0, min(1.0, rel))
                        max_bounce_angle = math.radians(75)
                        angle = rel * max_bounce_angle
                        speed = math.hypot(b.vel.x, b.vel.y)
                        b.vel.x = math.sin(angle) * speed
                        b.vel.y = -abs(math.cos(angle) * speed)
                        b.pos.y = self.paddle.rect.y - b.radius - 1
                        self.sfx_hit_paddle.play()

                    # Blocks
                    for block in self.blocks:
                        if not block.alive:
                            continue
                        if getattr(block, 'frozen', False):
                            continue  # Freeze special blocks if frozen

                        if block.rect.collidepoint(b.pos.x, b.pos.y - b.radius) or \
                        block.rect.collidepoint(b.pos.x, b.pos.y + b.radius) or \
                        block.rect.collidepoint(b.pos.x - b.radius, b.pos.y) or \
                        block.rect.collidepoint(b.pos.x + b.radius, b.pos.y):
                            overlap_x = (b.pos.x - max(block.rect.left, min(b.pos.x, block.rect.right)))
                            overlap_y = (b.pos.y - max(block.rect.top, min(b.pos.y, block.rect.bottom)))
                            if abs(overlap_x) > abs(overlap_y):
                                b.reflect_horizontal()
                            else:
                                b.reflect_vertical()
                            self.sfx_hit_block.play()

                            if isinstance(block, SpecialBlock):
                                self.current_question = self.qman.get_question(block.question_id)
                                self.show_question = True
                                # Keep block intact until question answered
                            else:
                                block.hit()
                                if not block.alive:
                                    # Apply score multiplier
                                    self.score += 10 * self.score_multiplier
                            break

                # Check balls lost off bottom
                for ball in list(self.balls):
                    if ball.pos.y - ball.radius > SCREEN_HEIGHT:
                        if self.shield_active:
                            ball.pos.x = self.paddle.x
                            ball.pos.y = self.paddle.y - 60
                            ball.vel.y = -abs(ball.vel.y)
                        else:
                            self.balls.remove(ball)
                            if len(self.balls) == 0:
                                self.lives -= 1
                                self.sfx_lose_life.play()
                                if self.lives <= 0:
                                    self.sfx_game_over.play()
                                    self.state = 'game_over'
                                    self.create_game_over_menu()
                                else:
                                    self.ball = Ball(self.paddle.x, self.paddle.y - 60, speed=self.ball_speed)
                                    self.balls = [self.ball]

                # update powerups timers
                for entry in list(self.active_powerups):
                    entry[1] -= dt
                    if entry[1] <= 0:
                        entry[0].remove(self)
                        self.active_powerups.remove(entry)

                # Check level clear
                if all(not b.alive for b in self.blocks):
                    self.level += 1
                    self.generate_level()

    def draw(self):
        self.screen.fill(BG_COLOR)

        if self.state == 'menu':
            self.draw_menu()
        elif self.state == 'difficulty_select':
            self.draw_difficulty_menu()
        elif self.state == 'game_over':
            self.draw_game_over()
        elif self.state == 'lessons':
            self.draw_lessons()
        elif self.state == 'playing':
            self.draw_playing()
            
        if self.countdown_active:
            msg = f"Resuming in {int(self.countdown_time_left) + 1}..."
            txt = self.large_font.render(msg, True, (255,255,80))
            self.screen.blit(txt, (SCREEN_WIDTH//2-txt.get_width()//2, 360))
            # Show explanation/feedback if you want
            expl = self.font.render(self.feedback_message, True, (220,220,220))
            self.screen.blit(expl, (SCREEN_WIDTH//2-expl.get_width()//2, 420))

    def draw_menu(self):
        title = self.large_font.render('PhysiBreak', True, TEXT_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 120)))
        sub = self.font.render('Learn physics while playing a classic arcade game', True, TEXT_COLOR)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH//2, 160)))

        for btn in self.menu_buttons:
            btn.draw(self.screen, self.font)

    def draw_difficulty_menu(self):
        title = self.large_font.render('Select Difficulty', True, TEXT_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 160)))
        for btn in self.difficulty_buttons:
            btn.draw(self.screen, self.font)

    def draw_game_over(self):
        title = self.large_font.render('Game Over', True, (255, 70, 70))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 200)))
        for btn in self.game_over_buttons:
            btn.draw(self.screen, self.font)
    
    def draw_lessons(self):
        lp = self.lessons[self.lesson_index]
        title = self.large_font.render(lp.title, True, TEXT_COLOR)
        self.screen.blit(title, (60, 40))
        y = 120
        max_line_width = SCREEN_WIDTH - 120  # or set your own padding
        for line in lp.lines:
            wrapped_lines = self.wrap_text(line, max_line_width, self.font)
            for wline in wrapped_lines:
                txt = self.font.render(wline, True, TEXT_COLOR)
                self.screen.blit(txt, (60, y))
                y += txt.get_height() + 6


        hint = self.font.render('Press LEFT/RIGHT to change lesson, ESC to go back', True, TEXT_COLOR)
        self.screen.blit(hint, (60, SCREEN_HEIGHT - 40))

    def draw_playing(self):
        # HUD
        hud = self.font.render(f'Score: {self.score}   Lives: {self.lives}   Level: {self.level}', True, TEXT_COLOR)
        self.screen.blit(hud, (18, 16))

        # Blocks
        for block in self.blocks:
            if block.alive:
                block.draw(self.screen)

        # paddle & ball
        self.paddle.draw(self.screen)
        for ball in self.balls:
            ball.draw(self.screen)

        # active powerups
        y = 40
        for entry in self.active_powerups:
            pu = entry[0]
            rem = entry[1]
            txt = self.font.render(f'{pu.name}: {rem:.1f}s', True, TEXT_COLOR)
            self.screen.blit(txt, (SCREEN_WIDTH - 220, y))
            y += txt.get_height() + 6

        if self.show_question and self.current_question:
            self.draw_question()

    # ------------------------
    # API for external tweak/testing
    # ------------------------
    def add_lesson(self, title, lines):
        self.lessons.append(LessonPage(title, lines))


# ------------------------
# Run if main
# ------------------------
if __name__ == '__main__':
    game = PhysiBreakGame()
    game.run()
